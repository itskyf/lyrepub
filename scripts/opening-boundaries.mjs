// Re-derive the Đêm hội Long Trì opening SMIL boundaries from the retained
// #15 CTC emissions. The align CLI cannot match the opening sentence (the
// music-covered years clause leaves no greedy-decodable anchors), so this
// anchors the forced alignment at the strong flanking words instead. The
// adopted boundaries and their rationale are recorded in
// docs/research/publication-validation.md.
//
// Isolated diagnostic pinned to the mise-managed @storyteller-platform/align
// 0.2.4 install: it imports that package's low-level modules, which the
// package public API does not expose, so it is not covered by unit tests.
//
// Usage: node scripts/opening-boundaries.mjs [emissions-dir]

import { existsSync, realpathSync } from "node:fs";
import { delimiter, dirname, join } from "node:path";
import { pathToFileURL } from "node:url";

const TRANSCRIPT =
	"Nhà văn Nguyễn Huy Tưởng, sinh năm 1912, mất năm 1960. Quê quán: Dục Tú, Đông Anh, Hà Nội.";
const EMISSIONS = process.argv[2] ?? "data/silver/issue-15/emissions";
// Decoding window: credit tail through the following sentence.
const WINDOW_FROM_SECONDS = 19;
const WINDOW_TO_SECONDS = 32;

const alignDist = () => {
	for (const dir of process.env.PATH.split(delimiter)) {
		const shim = join(dir, "align");
		if (existsSync(shim)) {
			// <…>/node_modules/.bin/align → <…>/node_modules/@storyteller-platform/align/dist
			return join(
				dirname(dirname(realpathSync(shim))),
				"@storyteller-platform/align/dist",
			);
		}
	}
	throw new Error("align executable not found on PATH");
};

const dist = alignDist();
const { EmissionsReader } = await import(
	pathToFileURL(join(dist, "emit/fs.js")).href
);
const { ctcGreedyDecode } = await import(
	pathToFileURL(join(dist, "align/ctc/greedyDecode.js")).href
);
const { ctcForcedAlign } = await import(
	pathToFileURL(join(dist, "align/ctc/forcedAlign.js")).href
);
const { slugify } = await import(
	pathToFileURL(join(dist, "align/slugify.js")).href
);
const { boundaryOffsetFrames } = await import(
	pathToFileURL(join(dist, "align/ctc/emissions.js")).href
);

const reader = await EmissionsReader.from(EMISSIONS);
const secondsPerFrame = reader.timings[0].secondsPerFrame;
const { start: startOffset, end: endOffset } = boundaryOffsetFrames(
	reader.timings[0],
);
const locale = new Intl.Locale("vi");
const slug = (await slugify(TRANSCRIPT, locale)).result;

// Anchors come from the same greedy decode the CLI search uses: first
// occurrence of each flanking word past the credit. The decoded text carries
// no separators while the slug joins words with "-".
const { text: decoded, frames: decodedFrames } = await ctcGreedyDecode(reader);
const anchor = (decodedNeedle, slugNeedle, notBeforeSeconds) => {
	for (
		let i = decoded.indexOf(decodedNeedle);
		i !== -1;
		i = decoded.indexOf(decodedNeedle, i + 1)
	) {
		if (decodedFrames[i] * secondsPerFrame >= notBeforeSeconds) {
			return { frame: decodedFrames[i], slugOffset: slug.indexOf(slugNeedle) };
		}
	}
	return null;
};
const anchors = [
	anchor("nhavang", "nha-van", 19),
	anchor("quequan", "que-quan", 24),
];
if (anchors.some((a) => a === null || a.slugOffset === -1)) {
	throw new Error("flanking anchors not found in decoded emissions");
}

const windowFrom = Math.round(WINDOW_FROM_SECONDS / secondsPerFrame);
const windowTo = Math.round(WINDOW_TO_SECONDS / secondsPerFrame);
const emissions = await reader.readFrames(windowFrom, windowTo);
const alignments = ctcForcedAlign(
	slug,
	emissions,
	anchors.map((a) => ({
		offset: a.slugOffset,
		position: a.frame - windowFrom,
	})),
	reader.vocab,
	reader.blankId,
);

// Map each transcript word onto its slug range, then collect label timings.
const words = [];
let slugPosition = 0;
for (const word of TRANSCRIPT.split(/\s+/)) {
	const bare = word.replaceAll(/[^\p{L}\p{N}]/gu, "");
	const wordSlug = bare ? (await slugify(bare, locale)).result : "";
	const found = wordSlug ? slug.indexOf(wordSlug, slugPosition) : slugPosition;
	const from = found === -1 ? slugPosition : found;
	const to = found === -1 ? slugPosition : found + wordSlug.length;
	words.push({ word, from, to });
	slugPosition = to;
}
const seconds = (labelIndex) => {
	const span = alignments.slice(labelIndex.from, labelIndex.to);
	const startFrame = span.map((l) => l.startFrame).at(0);
	const endFrame = span.map((l) => l.endFrame).at(-1);
	if (startFrame === undefined || endFrame === undefined) return null;
	return {
		start: (windowFrom + startFrame + startOffset) * secondsPerFrame,
		end: (windowFrom + endFrame + endOffset) * secondsPerFrame,
	};
};

const rounded = (value) => `${(Math.round(value * 10) / 10).toFixed(3)}s`;
for (const word of words) {
	const timing = seconds(word);
	console.log(
		timing
			? `${timing.start.toFixed(2).padStart(7)} ${timing.end.toFixed(2).padEnd(7)}  ${word.word}`
			: `${"unaligned".padStart(7)} ${"".padEnd(7)}  ${word.word}`,
	);
}
const boundaries = {};
for (const [name, word] of [
	["onset", "Nhà"],
	["name_onset", "Nguyễn"],
	["year_onset", "sinh"],
	["next_onset", "Quê"],
]) {
	boundaries[name] = rounded(seconds(words.find((w) => w.word === word)).start);
}
console.log(
	`\nadopted: ${boundaries.onset} / ${boundaries.name_onset} / ${boundaries.year_onset} / ${boundaries.next_onset} (s2 end tiles at next_onset)`,
);
