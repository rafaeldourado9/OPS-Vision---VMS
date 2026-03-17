FROM bluenviron/mediamtx:latest AS base

FROM alpine:3.21
COPY --from=base /mediamtx /mediamtx

RUN apk add --no-cache curl

ENTRYPOINT ["/mediamtx"]
