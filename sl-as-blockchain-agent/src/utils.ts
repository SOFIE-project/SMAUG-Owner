export interface OfferDetails {
    id: number,
    creatorEncryptionKey: string,
    creatorAuthKey?: string
}

export async function waitForEnter(message?: string) {
    const waitForEnter = require("wait-for-enter");
    message = message || "Press Enter to continue..."
    console.log(message)
    await waitForEnter()
}

export interface EnvVariables {
    ILAddress: string,
    ILABIPath: string,
    ethereumILAddress: string,
    MPAddress: string,
    MPABIPath: string,
    ethereumMPAddress: string,
    PDSBackendAddress: string,
    PDSAddress: string,
    PDSABIPath: string,
    PDSOwner: string,
    isInteractive: boolean
}