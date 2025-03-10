const { Gateway, Wallets } = require('fabric-network');
const { FabricCAServices } = require('fabric-ca-client');
const path = require('path');
const fs = require('fs');

async function invokeChaincode(func, args) {
    try {
        const walletPath = path.join(__dirname, 'wallet');
        const wallet = await Wallets.newFileSystemWallet(walletPath);
        const ccpPath = path.join(__dirname, '..\\fabric-samples\\test-network\\organizations\\peerOrganizations\\org1.example.com\\connection-org1.json');
        const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));

        if (!(await wallet.get('admin'))) {
            process.stderr.write('Admin identity not found, enrolling admin...\n');
            const caInfo = ccp.certificateAuthorities['ca.org1.example.com'];
            const ca = new FabricCAServices(caInfo.url);
            const enrollment = await ca.enroll({ enrollmentID: 'admin', enrollmentSecret: 'adminpw' });
            const x509Identity = {
                credentials: {
                    certificate: enrollment.certificate,
                    privateKey: enrollment.key.toBytes(),
                },
                mspId: 'Org1MSP',
                type: 'X.509',
            };
            await wallet.put('admin', x509Identity);
            process.stderr.write('Admin enrolled successfully\n');
        }

        const gateway = new Gateway();
        await gateway.connect(ccp, { wallet, identity: 'admin', discovery: { enabled: true, asLocalhost: true } });
        const network = await gateway.getNetwork('energychannel');
        const contract = network.getContract('energytrading');

        const result = await contract.submitTransaction(func, ...args);
        await gateway.disconnect();
        return JSON.parse(result.toString());
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
}

async function queryChaincode(func, args) {
    try {
        const walletPath = path.join(__dirname, 'wallet');
        const wallet = await Wallets.newFileSystemWallet(walletPath);
        const ccpPath = path.join(__dirname, '..\\fabric-samples\\test-network\\organizations\\peerOrganizations\\org1.example.com\\connection-org1.json');
        const ccp = JSON.parse(fs.readFileSync(ccpPath, 'utf8'));

        if (!(await wallet.get('admin'))) {
            process.stderr.write('Admin identity not found, enrolling admin...\n');
            const caInfo = ccp.certificateAuthorities['ca.org1.example.com'];
            const ca = new FabricCAServices(caInfo.url);
            const enrollment = await ca.enroll({ enrollmentID: 'admin', enrollmentSecret: 'adminpw' });
            const x509Identity = {
                credentials: {
                    certificate: enrollment.certificate,
                    privateKey: enrollment.key.toBytes(),
                },
                mspId: 'Org1MSP',
                type: 'X.509',
            };
            await wallet.put('admin', x509Identity);
            process.stderr.write('Admin enrolled successfully\n');
        }

        const gateway = new Gateway();
        await gateway.connect(ccp, { wallet, identity: 'admin', discovery: { enabled: true, asLocalhost: true } });
        const network = await gateway.getNetwork('energychannel');
        const contract = network.getContract('energytrading');

        const result = await contract.evaluateTransaction(func, ...args);
        await gateway.disconnect();
        return JSON.parse(result.toString());
    } catch (error) {
        return { status: "ERROR", message: error.message };
    }
}

async function main() {
    const func = process.argv[2];
    const args = process.argv.slice(3);

    if (!func) {
        console.log(JSON.stringify({ status: "ERROR", message: "No function specified" }));
        return;
    }

    let result;
    if (func.startsWith('get')) {
        result = await queryChaincode(func, args);
    } else {
        result = await invokeChaincode(func, args);
    }
    console.log(JSON.stringify(result));
}

if (require.main === module) {
    main().catch(err => {
        console.log(JSON.stringify({ status: "ERROR", message: err.message }));
        process.exit(1);
    });
}