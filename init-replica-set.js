// MongoDB Replica Set Initialization Script
// This script initializes the replica set if it hasn't been initialized yet

try {
  var status = rs.status();
  print('Replica set already initialized');
  printjson(status);
} catch (e) {
  if (e.message.includes('no replset config has been received') || 
      e.message.includes('NotYetInitialized')) {
    print('Initializing replica set...');
    var result = rs.initiate({
      _id: 'rs0',
      members: [
        { _id: 0, host: 'localhost:27017' }
      ]
    });
    print('Replica set initialization result:');
    printjson(result);
    print('Waiting for replica set to be ready...');
    // Wait a bit for the replica set to initialize
    sleep(2000);
    print('Replica set initialized successfully!');
  } else {
    print('Error checking replica set status: ' + e.message);
  }
}

