FROM node:lts-alpine3.12

ARG PROJECT_PATH="/sl-as-blockchain-agent"

RUN mkdir -p ${PROJECT_PATH}
WORKDIR ${PROJECT_PATH}
COPY package.json tsconfig.json ./
COPY ./config/abi ./config/abi
RUN npm install --unsafe-perm

COPY docker.env ./
COPY ./src ./src

ENTRYPOINT [ "/usr/local/bin/npm", "run", "demo:docker" ]