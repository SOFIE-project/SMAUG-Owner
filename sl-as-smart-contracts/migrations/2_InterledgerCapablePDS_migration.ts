const InterledgerProxy = artifacts.require("InterledgerProxyImplementation")
const InterledgerCapablePDS = artifacts.require("InterledgerCapablePDS")

module.exports = (async (deployer, network) => {
    let ILProxyAddress: string

    if (network != "authorisation") {
        console.log("Development network. Deploying InterledgerProxy smart contract.")
        await deployer.deploy(InterledgerProxy)
        ILProxyAddress = (await InterledgerProxy.deployed()).address
    } else {
        let ILAddressArgIndex = process.argv.indexOf("--il-address")
        if (ILAddressArgIndex == -1) {
            throw "Missing --il-address argument."
        }
        ILProxyAddress = process.argv[ILAddressArgIndex+1]
        if (ILProxyAddress == undefined) {
            throw "Missing value for --il-address argument."
        }
        if (!web3.utils.isAddress(ILProxyAddress)) {
            throw "Value for --il-address argument not a valid address."
        }
    }
    console.log(`Deploying PDS linked to ILProxy at address: ${ILProxyAddress}`))
    await deployer.deploy(InterledgerCapablePDS, ILProxyAddress)
}) as Truffle.Migration

// because of https://stackoverflow.com/questions/40900791/cannot-redeclare-block-scoped-variable-in-unrelated-files
export {}