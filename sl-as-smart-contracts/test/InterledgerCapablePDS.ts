import { start } from "repl"

const { expectEvent } = require("@openzeppelin/test-helpers")

contract("InterledgerCapablePDS", async accounts => {
    const InterledgerCapablePDS = artifacts.require("InterledgerCapablePDS")
    const InterledgerProxy = artifacts.require("InterledgerProxyImplementation")

    it("constructor & getInterledgerSmartContractAddress", async () => {
        let interledgerProxy = await InterledgerProxy.deployed()
        let contract = await InterledgerCapablePDS.new(interledgerProxy.address)
        let interledgerProxysmartContractAddress = await contract.getInterledgerSmartContractAddress()
        assert.equal(interledgerProxysmartContractAddress, interledgerProxy.address, "Wrong address for IL proxy returned.")
    })

    it("changeInterledgerSmartContractAddress", async() => {
        let owner = accounts[0]
        let interledgerProxy = await InterledgerProxy.deployed()
        let contract = await InterledgerCapablePDS.new(interledgerProxy.address, {from: owner})

        // Valid operation

        let newInterledgerProxy = await InterledgerProxy.new()
        await contract.changeInterledgerSmartContractAddress(newInterledgerProxy.address, {from: owner})
        assert.equal(newInterledgerProxy.address, await contract.getInterledgerSmartContractAddress(), "Wrong interledger proxy address returned.")

        // Anauthorised user

        let unauthorisedUser = accounts[1]
        try {
            await contract.changeInterledgerSmartContractAddress(interledgerProxy.address, {from: unauthorisedUser})
            assert.isTrue(false, "Call should fail and execution should not get here.")
        } catch (e) {
            assert.equal(e.reason, "Ownable: caller is not the owner", "Some unexpected excpetion has been thrown.")
        }
    })

    it("new_token", async () => {
        let owner = accounts[0]
        let interledgerProxy = await InterledgerProxy.deployed()
        let contract = await InterledgerCapablePDS.new(interledgerProxy.address, {from: owner})

        // Valid flow

        let metadata = web3.eth.abi.encodeParameter("uint256", 1)
        let encryptedToken = web3.eth.abi.encodeParameter("string", "1")
        let tx = await contract.new_token(metadata, encryptedToken, {from: owner})
        let events = tx.logs
        // assert.equal(events.length, 1, "InterledgerCapablePDS smart contract emitted the wrong number of events.")
        let tokenIndex = parseInt(events[0].args.index)
        let tokenMetadata = events[0].args.metadata
        assert.equal(tokenIndex, 0)
        assert.equal(tokenMetadata, web3.utils.soliditySha3(metadata))
        let metadata2 = web3.eth.abi.encodeParameter("uint256", 2)
        let encryptedToken2 = web3.eth.abi.encodeParameter("string", "2")
        tx = await contract.new_token(metadata2, encryptedToken2, {from: owner})
        tokenIndex = parseInt(tx.logs[0].args.index)
        assert.equal(tokenIndex, 1)

        // Unauthorised user

        let unauthorisedUser = accounts[1]
        try {
            await contract.new_token(metadata, encryptedToken, {from: unauthorisedUser})
            assert.isTrue(false, "Call should fail and execution should not get here.")
        } catch (e) {
            assert.equal(e.reason, "Ownable: caller is not the owner", "Some unexpected excpetion has been thrown.")
        }
    })

    it("advertiseTokens", async () => {
        let owner = accounts[0]
        let interledgerProxy = await InterledgerProxy.deployed()
        let contract = await InterledgerCapablePDS.new(interledgerProxy.address, {from: owner})
        
        // Valid flow

        let metadata1 = 1
        let encryptedToken1 = "asdfgh12312312312"
        let tx = await contract.new_token(web3.eth.abi.encodeParameter("uint256", metadata1), web3.eth.abi.encodeParameter("string", encryptedToken1), {from: owner})
        let token1Index = parseInt(tx.logs[0].args.index)
        let metadata2 = 52385732951
        let encryptedToken2 = "asd"
        tx = await contract.new_token(web3.eth.abi.encodeParameter("uint256", metadata2), web3.eth.abi.encodeParameter("string", encryptedToken2), {from: owner})
        let token2Index = parseInt(tx.logs[0].args.index)
        tx = await contract.advertiseTokens([token1Index, token2Index], {from: owner})
        let interledgerProxyEvent = await expectEvent.inTransaction(tx.tx, interledgerProxy, "InterledgerEventSending", {})
        assert.isNotNull(interledgerProxyEvent, "One InterledgerEventSending should be emitted.")
        assert.equal(interledgerProxyEvent.args.id, 0, "InterledgerEventSending emitted a wrong event ID.")
        let interledgerPayload = interledgerProxyEvent.args.data as string
        interledgerPayload = interledgerPayload.substr(2)            // Remove 0x prefix
        let metadata1InterledgerLength = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(0, 64))
        let startIndex = 64
        let metadata1Interledger = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(startIndex, metadata1InterledgerLength*2))
        startIndex += metadata1InterledgerLength*2
        assert.equal(metadata1Interledger, metadata1, "Metadata value of Interledger different from the one expected")
        let encryptedToken1InterledgerLength = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(startIndex, 64))
        startIndex += 64
        let encryptedToken1Interledger = web3.eth.abi.decodeParameter("string", "0x" + interledgerPayload.substr(startIndex, encryptedToken1InterledgerLength*2))
        startIndex += encryptedToken1InterledgerLength*2
        assert.equal(encryptedToken1Interledger, encryptedToken1, "Encrypted token value of Interledger different from the one expected")
        let metadata2InterledgerLength = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(startIndex, 64))
        startIndex += 64
        let metadata2Interledger = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(startIndex, metadata2InterledgerLength*2))
        startIndex += metadata2InterledgerLength*2
        assert.equal(metadata2Interledger, metadata2, "Metadata value of Interledger different from the one expected")
        let encryptedToken2InterledgerLength = web3.eth.abi.decodeParameter("uint256", "0x" + interledgerPayload.substr(startIndex, 64))
        startIndex += 64
        let encryptedToken2Interledger = web3.eth.abi.decodeParameter("string", "0x" + interledgerPayload.substr(startIndex, encryptedToken2InterledgerLength*2))
        startIndex += encryptedToken1InterledgerLength*2
        assert.equal(encryptedToken2Interledger, encryptedToken2, "Encrypted token value of Interledger different from the one expected")

        // Invalid token index

        try {
            await contract.advertiseTokens([99999], {from: owner})
            assert.isTrue(false, "Call should fail and execution should not get here.")
        } catch (e) {
            assert.equal(e.reason, "Index given contains either no token or a token already Interledged.", "Some unexpected excpetion has been thrown.")
        }

        // Unauthorised user

        let unauthorisedUser = accounts[1]
        try {
            await contract.new_token("0xaa", "0xab", {from: unauthorisedUser})
            assert.isTrue(false, "Call should fail and execution should not get here.")
        } catch (e) {
            assert.equal(e.reason, "Ownable: caller is not the owner", "Some unexpected excpetion has been thrown.")
        }        
    })
})