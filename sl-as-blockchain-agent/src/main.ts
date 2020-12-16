import Web3 from "web3"
import fs from "fs"

import { InterledgerProxyImplementation } from "../types/web3-v1-contracts/InterledgerProxyImplementation"
import { Pds as PDS } from "../types/web3-v1-contracts/PDS"
import { OfferDetails, waitForEnter, EnvVariables } from "./utils"
import { URL, URLSearchParams } from "url"
import fetch from "node-fetch"
import { SmaugMarketPlace } from "../types/web3-v1-contracts/SMAUGMarketPlace"
import { sys } from "typescript"

var web3AuthorisationInstance: Web3
var web3MarketplaceInstance: Web3
var pdsContractOwner: string
var InterledgerProxyImplementationInstance: InterledgerProxyImplementation
var SMAUGMarketplaceInstance: SmaugMarketPlace
var PDSContractInstance: PDS
var PDSEndpointAddress: URL
var interactive: boolean

main().catch(error => {
    console.error(error)
    process.exit(1)
})

async function main(): Promise<void> {

    const variables = parseAndReturnEnvVariables(process.env)

    console.log(`Starting agent in ${variables.isInteractive ? "" : "non-"}interactive mode...`)

    console.log(`- Connecting to ${variables.MPAddress} (marketplace blockchain) and ${variables.ILAddress} (authorisation blockchain)...`)
    web3AuthorisationInstance = new Web3(variables.ethereumILAddress)
    web3MarketplaceInstance = new Web3(variables.ethereumMPAddress)

    console.log(`- Retrieving Interledger contract at ${variables.ILAddress}...`)
    console.log(`- Retrieving SMAUG Marketplace contract at ${variables.MPAddress}...`)
    InterledgerProxyImplementationInstance = (new web3AuthorisationInstance.eth.Contract(JSON.parse(fs.readFileSync(variables.ILABIPath).toString()), variables.ILAddress) as any) as InterledgerProxyImplementation
    PDSContractInstance = (new web3AuthorisationInstance.eth.Contract(JSON.parse(fs.readFileSync(variables.PDSABIPath).toString()), variables.PDSAddress) as any) as PDS
    SMAUGMarketplaceInstance = (new web3MarketplaceInstance.eth.Contract(JSON.parse(fs.readFileSync(variables.MPABIPath).toString()), variables.MPAddress) as any) as SmaugMarketPlace
    interactive = variables.isInteractive

    if (!Web3.utils.isAddress(variables.PDSOwner)) {
        throw Error("PDS owner account is not a valid address format.")
    }
    pdsContractOwner = variables.PDSOwner

    try {
        PDSEndpointAddress = new URL(variables.PDSBackendAddress)
    } catch(err) {
        throw new Error("PDS address is not a valid HTTP(S) address.")
    }

    await listenForInterledgerEvents(true)
}

function parseAndReturnEnvVariables(environment: NodeJS.ProcessEnv): EnvVariables {
    const ILAddress = process.env["IL_ADDRESS"] as string 
    const ILABIPath = process.env["IL_ABI_PATH"] as string
    const ethereumILAddress = process.env["ETHEREUM_IL_ADDRESS"] as string
    const MPAddress = process.env["MP_ADDRESS"] as string
    const MPABIPath = process.env["MP_ABI_PATH"] as string
    const ethereumMPAddress = process.env["ETHEREUM_MP_ADDRESS"] as string
    const PDSBackendAddress = process.env["PDS_BACKEND_ADDRESS"] as string
    const PDSAddress = process.env["PDS_ADDRESS"] as string
    const PDSABIPath = process.env["PDS_ABI_PATH"] as string
    const PDSOwner = process.env["PDS_OWNER"] as string
    const isInteractive = process.env["INTERACTIVE"] as string === "true"

    if (ILAddress == undefined) {
        console.error("IL_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (ILABIPath == undefined) {
        console.error("IL_ABI_PATH env variable missing.")
        sys.exit(1)
    }
    if (ethereumILAddress == undefined) {
        console.error("ETHEREUM_IL_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (MPAddress == undefined) {
        console.error("MP_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (MPABIPath == undefined) {
        console.error("MP_ABI_PATH env variable missing.")
        sys.exit(1)
    }
    if (ethereumMPAddress == undefined) {
        console.error("ETHEREUM_MP_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (PDSBackendAddress == undefined) {
        console.error("PDS_BACKEND_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (PDSAddress == undefined) {
        console.error("PDS_ADDRESS env variable missing.")
        sys.exit(1)
    }
    if (PDSABIPath == undefined) {
        console.error("PDS_ABI_PATH env variable missing.")
        sys.exit(1)
    }
    if (PDSOwner == undefined) {
        console.error("PDS_OWNER env variable missing.")
        sys.exit(1)
    }
    
    return { ILAddress, ILABIPath, ethereumILAddress, MPAddress, MPABIPath, ethereumMPAddress, PDSBackendAddress, PDSAddress, PDSABIPath, PDSOwner, isInteractive }
}

async function listenForInterledgerEvents(debug: boolean = false): Promise<void> {
    debug && console.log("\nListening for InterledgerDataReceived events...")
    
    InterledgerProxyImplementationInstance.events.InterledgerDataReceived(async (error, event) => {
        if (error != null) {
            console.error(`${error.name}\n${error.message}`)
            return
        }
        console.log(`New ${event.event} event received!`)
        console.log(event)
        let rawEventData = event.returnValues.data
        let offerDetails = getOfferDetails(rawEventData)
        console.log("Decoded event data:")
        console.log(offerDetails)
        interactive && await waitForEnter()
        await logTokensFor(offerDetails)
    })

    process.on("SIGINT", () => {
        console.log("\nBye!")
        process.exit(0)
    })
}

function getOfferDetails(interledgerPayload: string): OfferDetails[] {

    interledgerPayload = interledgerPayload.substr(2)                               // Remove 0x prefix
    let result: OfferDetails[] = []
    let index = 0

    // /*
    //     Each entry (each offer detail) is structured in the following way:
    //         - 1 byte (2 HEX chars) to indicate if there is an auth key or not
    //         - 32 bytes (64 HEX chars) for the offer ID
    //         - 32 bytes (64 HEX chars) for the offer encryption key
    //         - 32 bytes (64 HEX chars) for the offer auth key (OPTIONAL)
    //     No check is performed, for the time being
    // */
    while (index < interledgerPayload.length) {
        let isAuthKeyPresent = Web3.utils.hexToNumber("0x" + interledgerPayload.substr(index, 2)) == 1
        index += 2
        let offerID = Web3.utils.hexToNumber("0x" + interledgerPayload.substr(index, 64))
        index += 64
        let offerEncryptionKey = "0x" + interledgerPayload.substr(index, 64)
        index += 64

        let offerDetails: OfferDetails = {id: offerID, creatorEncryptionKey: offerEncryptionKey}

        if (isAuthKeyPresent) {
            offerDetails.creatorAuthKey = "0x" + interledgerPayload.substr(index, 64)
            index += 64
        }

        result.push(offerDetails)
    }

    return result
}

async function logTokensFor(offerDetails: OfferDetails[]): Promise<void> {
    let tokenIndices = await new Promise<number[]>(async resolve => {
        let pendingOffersMetadata: Set<string> = new Set(offerDetails.map(offer => Web3.utils.soliditySha3(web3AuthorisationInstance.eth.abi.encodeParameter("uint256", offer.id)) as string))
        let offerTokenIndices: number[] = []
        await PDSContractInstance.events.token_added(async (error, event) => {
            let tokenIndex = parseInt(event.returnValues.index)
            let tokenMetadata = event.returnValues.metadata
            if (!pendingOffersMetadata.has(tokenMetadata)) { return }
            offerTokenIndices.push(tokenIndex)
            if (offerTokenIndices.length == offerDetails.length) {
                resolve(offerTokenIndices)
                return
            }
        })
        console.log(`Issuing tokens for offers [${offerDetails.map(details => details.id).toString()}]...`)
        for (let details of offerDetails) {
            let metadata = web3AuthorisationInstance.eth.abi.encodeParameter("uint256", details.id)
            let offerDetails = await SMAUGMarketplaceInstance.methods.getOffer(details.id).call()
            let offerExtraDetails = await SMAUGMarketplaceInstance.methods.getOfferExtra(details.id).call()
            let requestExtraDetails = await SMAUGMarketplaceInstance.methods.getRequestExtra(offerDetails.requestID).call()
            let offerStartingTime = new Date(parseInt(offerExtraDetails.startOfRentTime)*1000)
            let offerEndTime = new Date(offerStartingTime.getTime() + parseInt(offerExtraDetails.duration)*60*1000) // offer duration is in minutes. Must be converted to milliseconds
            let lockerID = requestExtraDetails.lockerID

            let requestParams = new URLSearchParams()
            requestParams.append("grant-type", "auth_code")
            requestParams.append("grant", "shared_secret_key")
            requestParams.append("log-token", `${metadata}`)
            requestParams.append("enc-key", details.creatorEncryptionKey.substr(2))     // Remove leading 0x
            requestParams.append("metadata", JSON.stringify({nbf: offerStartingTime.toISOString(), exp: offerEndTime.toISOString(), aud: lockerID}))
            await fetch(`${PDSEndpointAddress}/gettoken`, {method: "POST", body: requestParams})
        }
    })

    if (interactive) {
        await waitForEnter("Tokens logged on the authorisation blockchain. Press Enter to trigger Interledger back to marketplace:")
    } else {
        console.log("Tokens logged on the authorisation blockchain. Triggering Interledger back to marketplace...")
    }
    
    console.log(`Triggering interledger for issued tokens by calling PDSSmartContract::advertiseTokens(tokenIndices), which calls InterledgerProxySmartContract::triggerInterledger(interledgerPayload)...`)
    await PDSContractInstance.methods.advertiseTokens(tokenIndices).send({from: pdsContractOwner, gas: 2000000})
    console.log("Interledger event triggered. Token creation process completed!\n")
}