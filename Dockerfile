# This will build the currently checked out version
#
# we use an intermediate image to build this image. it will make the resulting
# image a bit smaller.
#
# you can build the image with:
#
#   docker build . -t contracts
#
# The resulting image can be used to deploy contracts with something like the
# following command:
#
# docker run --net=host  --rm -it contracts test --file addresses.json
#

FROM ubuntu:18.04 as builder
# python needs LANG
ENV LANG C.UTF-8
RUN apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends libssl-dev curl python3 python3-distutils libpq5 ca-certificates \
               pkg-config libsecp256k1-dev python3-dev python3-venv git build-essential libpq-dev && \
    rm -rf /var/lib/apt/lists/* && \
    curl -L -o /usr/bin/solc https://github.com/ethereum/solidity/releases/download/v0.4.25/solc-static-linux && \
    chmod +x /usr/bin/solc

# cache /opt/contracts with requirements installed
RUN python3 -m venv /opt/contracts
WORKDIR /contracts
ENV PATH "/opt/contracts/bin:${PATH}"
COPY ./constraints.txt /contracts/constraints.txt
RUN pip install -c constraints.txt pip wheel setuptools
COPY ./requirements.txt /contracts/requirements.txt

# remove development dependencies from the end of the file and install requierements
RUN sed -i -e '/development dependencies/q' requirements.txt && \
    pip install -c constraints.txt -r requirements.txt

COPY . /contracts
RUN pip install -c constraints.txt setuptools_scm
RUN make install-non-editable
RUN python -c 'import pkg_resources; print(pkg_resources.get_distribution("trustlines-contracts-deploy").version)' >/opt/contracts/VERSION


FROM ubuntu:18.04 as runner
ENV LANG C.UTF-8
ENV PATH "/opt/contracts/bin:${PATH}"
RUN apt-get -y update && \
    apt-get -y install  --no-install-recommends libssl1.1 python3 python3-distutils libsecp256k1-0 && \
    rm -rf /var/lib/apt/lists/* && \
    ln -s /opt/contracts/bin/tl-deploy /usr/local/bin/

FROM runner
COPY --from=builder /opt/contracts /opt/contracts
WORKDIR /opt/contracts
ENTRYPOINT ["tl-deploy"]
CMD ["test"]
