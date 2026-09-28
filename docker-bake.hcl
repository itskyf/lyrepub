variable "VALIDATOR_OUT" {
  default = "data/validator-images"
}

group "validators" {
  targets = ["epubcheck", "ace"]
}

target "epubcheck" {
  context    = "https://github.com/w3c/epubcheck.git?tag=v5.4.0&checksum=a51f751b986ac424488586aae75c43d047bbdc53"
  dockerfile = "Dockerfile"
  tags       = ["localhost/lyrepub-epubcheck:5.4.0"]
  output = [{
    type = "docker"
    dest = "${VALIDATOR_OUT}/epubcheck-5.4.0.tar"
  }]
}

target "ace" {
  context    = "containers"
  dockerfile = "Containerfile.ace"
  tags       = ["localhost/lyrepub-ace:1.4.6"]
  output = [{
    type = "docker"
    dest = "${VALIDATOR_OUT}/ace-1.4.6.tar"
  }]
}
