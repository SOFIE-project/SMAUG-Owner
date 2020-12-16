# SMAUG Smart Locker Authorization Server Blockchain Agent


This component supports the services of the smart locker authorization server by listening on the authorisation blockchain for [InterledgerDataReceived](https://github.com/SOFIE-project/SMAUG-Marketplace/blob/master/il-smart-contracts/contracts/interfaces/InterledgerProxy.sol) events, and interacting with the [PDS smart contract](../sl-as-pds/contract/PDS.sol) to log access tokens.

## Deployment
### Fresh install

When the project is cloned for the first time, run `npm install`. This will install all the needed `npm` dependencies, as well as generate all the [Typechain](https://github.com/ethereum-ts/TypeChain) typescript bindings needed for development.

### Run

> Before running the demo, the ABI for the [PDS smart contract](../sl-as-pds/contract/PDS.sol) and the [Interledger smart contract](https://github.com/SOFIE-project/SMAUG-Marketplace/blob/master/il-smart-contracts/contracts/InterledgerProxyImplementation.sol) must be copied in `config/abi`. For convenience, the latest ABI is already present in the folder.

The demo application relies on a set of environment variables for its execution. Specifically, these variables are:

```
IL_ADDRESS= -> The Ethereum address of the Interledger Proxy Smart Contract
IL_ABI_PATH -> The path to the ABI definition for the Interledger Proxy Smart Contract
ETHEREUM_IL_ADDRESS -> The address of the authorization blockchain node to use
MP_ADDRESS -> The Ethereum address of the SMAUG marketplace smart contract (only used for demo purposes)
MP_ABI_PATH-> The path to the ABI definition for the SMAUG marketplace smart contract
ETHEREUM_MP_ADDRESS -> The address of the marketplace blockchain node to use
PDS_BACKEND_ADDRESS -> The URL of the SL AS PDS to query to generate new access tokens
PDS_ADDRESS -> The Ehtereum address of the SL AS PDS Smart Contract on the authorization blockchain
PDS_ABI_PATH -> The path to the ABI definition for the SL AS PDS Smart Contract
PDS_OWNER -> The Ethereum address of the account that will trigger the Interledger procedure by calling the PDS SL AS Smart Contract
INTERACTIVE -> Boolean indicating whether any interaction with the authorization blockchain requires manual confirmation (True) or not (False)
```

The demo application can be run by executing `npm run demo:local`, which uses the default values declared in `local.env`. A pre-requisite for the demo to work is that the two blockchains must be deployed, and all the needed smart contracts on them. For instructions on how to set up a demo [Docker Compose](https://docs.docker.com/compose/) environment, please see the [SMAUG Deployment repository](https://github.com/SOFIE-project/SMAUG-Deployment).

>At the moment, the blockchain agent needs info about the marketplace smart contract to retrieve additional information about an offer (start and end time). Due to lack of time, this is the quickest solution implemented. In the ideal world, all the content that the agent might ever need, including offer start and end time, would be passed with the Interledger event as part of its payload.