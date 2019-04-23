FROM alpine

WORKDIR /src

CMD ["python3", "-um", "japronto", "run.app"]

RUN apk add --update python3

ADD requirements.txt ./

RUN apk add --no-cache --virtual .build-deps build-base python3-dev git \
    && pip3 --no-cache install -r requirements.txt \
	&& apk del .build-deps \
	&& rm -rf /var/cache/apk/*


ADD *.py /src/