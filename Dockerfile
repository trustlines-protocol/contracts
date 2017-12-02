FROM python:3.5

RUN apt-get update && \
    apt-get install -y libssl-dev curl

RUN curl -L -o /usr/bin/solc https://github.com/ethereum/solidity/releases/download/v0.4.16/solc-static-linux && \
    chmod +x /usr/bin/solc

WORKDIR /contracts

COPY . /contracts

RUN pip install .

ENTRYPOINT [ "python"]
CMD ["deploy/deploy_testnetwork.py"] 
