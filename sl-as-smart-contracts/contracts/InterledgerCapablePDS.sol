pragma solidity ^0.5.0;

import { PDS } from "sofie-pds/PDS.sol";
import { InterledgerProxyImplementation } from "smaug-interledger-smart-contracts/contracts/InterledgerProxyImplementation.sol";

contract InterledgerCapablePDS is PDS {

    InterledgerProxyImplementation private interledgerSmartContract;

    mapping(uint => bool) private pendingOffers;    // Index in super.tokens -> bool if exists (not yet advertised with Interledger)

    constructor (address interledgerAddress) public {
        changeInterledgerSmartContractAddress(interledgerAddress);
    }

    function changeInterledgerSmartContractAddress(address newAddress) public onlyOwner {
        interledgerSmartContract = InterledgerProxyImplementation(newAddress);
    }

    function getInterledgerSmartContractAddress() public view returns (address) {
        return address(interledgerSmartContract);
    }

    function new_token(bytes memory metadata, bytes memory enc_token) public onlyOwner {
        super.new_token(metadata, enc_token);
        pendingOffers[tokens.length-1] = true; // Mark the generated token as not yet advertised with Interledger
    }

    // Not checked for now, but each array of indices should contain offers for the same request
    function advertiseTokens(uint[] memory tokenIndices) public onlyOwner {
        bytes memory interledgerPayload = new bytes(0);

        for (uint i = 0; i < tokenIndices.length; i++) {
            require(
                pendingOffers[tokenIndices[i]],
                "Index given contains either no token or a token already Interledged."
            );
            delete pendingOffers[tokenIndices[i]];
            interledgerPayload = abi.encodePacked(interledgerPayload, createInterledgerPayload(tokens[tokenIndices[i]]));
        }

        interledgerSmartContract.triggerInterledger(interledgerPayload);
    }

    function createInterledgerPayload(token_entry storage entry) private view returns (bytes memory) {
        return abi.encodePacked(entry.metadata.length, entry.metadata, entry.enc_token.length, entry.enc_token);
    }
}