# Synthetic TLS fixture

This certificate and private key are public test data, generated solely for the loopback
scripted provider in `test_model_transport_environment.py`. They carry no production authority
or credentials. Never install this CA in a user or system trust store. The test loads it only
into an explicit, short-lived SSL context and verifies that ambient CA configuration is ignored.
