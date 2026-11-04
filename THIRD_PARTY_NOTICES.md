# Third-party notices

Original integration and router code are distributed under the root MIT license.

The gateway container includes [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent), distributed under the MIT license. Its source, copyright notice, and license remain in the upstream image; the Dockerfile carries a small documented modification to credential classification. Preserve these upstream notices when redistributing the image.

The router uses Python's standard library and the pinned official Python Alpine image. Base images contain additional operating-system and language-runtime components under their respective licenses. The root license covers this project's original material; it does not replace licenses of container dependencies.

The gateway also includes [Tini v0.19.0](https://github.com/krallin/tini/tree/v0.19.0), MIT licensed. Its release executable is independently checksum-pinned rather than using the base image compatibility wrapper. Its copyright and license are included in `tini-LICENSE` beside these notices.
