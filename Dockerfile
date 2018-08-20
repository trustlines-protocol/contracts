FROM ubuntu:18.04 as ubuntu-python
# python needs LANG
ENV LANG C.UTF-8
RUN apt-get -y update && \
    apt-get -y dist-upgrade && \
    apt-get -y install --no-install-recommends libssl-dev curl python3 python3-distutils libpq5 ca-certificates && \
    curl -L -o /usr/bin/solc https://github.com/ethereum/solidity/releases/download/v0.4.21/solc-static-linux && \
    chmod +x /usr/bin/solc

FROM ubuntu-python AS builder

RUN apt-get install -y --no-install-recommends pkg-config libsecp256k1-dev python3-dev python3-venv git build-essential libpq-dev

RUN python3 -m venv /opt/contracts
WORKDIR /opt/contracts
RUN bin/pip install pip==18.0.0 setuptools==40.0.0

COPY ./requirements.txt /contracts/requirements.txt
COPY ./constraints.txt /contracts/constraints.txt

WORKDIR /contracts
# remove development dependencies from the end of the file and install requierements
RUN sed -i -e '/development dependencies/q' requirements.txt && \
    /opt/contracts/bin/pip install -c constraints.txt -r requirements.txt

COPY . /contracts

RUN /opt/contracts/bin/pip install -c constraints.txt .
RUN /opt/contracts/bin/python -c 'import pkg_resources; print(pkg_resources.get_distribution("trustlines-contracts").version)' >/opt/contracts/VERSION

FROM ubuntu-python
COPY --from=builder /opt/contracts /opt/contracts
RUN ln -s /opt/contracts/bin/tl-deploy /usr/local/bin/
WORKDIR /opt/contracts

ENTRYPOINT [ "tl-deploy"]
CMD ["test"]
