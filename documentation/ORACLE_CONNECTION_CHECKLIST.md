# Oracle Connection Checklist

## Configuration Status

### 1. Environment Variables ✅
- `.env` file has been updated with the correct configuration:
  ```
  ORACLE_USER=admin
  ORACLE_PASSWORD=your_actual_password_here
  ORACLE_DSN=brvdb1_medium (also tried brvdb1_high and brvdb1_tp)
  ORACLE_WALLET_LOCATION=wallet
  ```

### 2. Test Connection Script ✅
- `test_conn.py` has been updated to match the recommended script:
  ```python
  import oracledb
  import os
  from dotenv import load_dotenv

  # Load env variables
  load_dotenv()

  # Set TNS_ADMIN (required for Thin mode)
  wallet_path = os.path.join(os.getcwd(), os.getenv("ORACLE_WALLET_LOCATION"))
  os.environ["TNS_ADMIN"] = wallet_path
  print(f"TNS_ADMIN set to: {wallet_path}")

  # Use Thin Mode (no external client required)
  oracledb.thin = True

  # Debug Test: List available DSNs
  from pathlib import Path
  tns_path = Path(wallet_path) / "tnsnames.ora"
  print(f"\n🔍 Available DSNs:\n{tns_path.read_text()}")

  # Connect
  conn = oracledb.connect(
      user=os.getenv("ORACLE_USER"),
      password=os.getenv("ORACLE_PASSWORD"),
      dsn=os.getenv("ORACLE_DSN"),
      config_dir=wallet_path
  )

  print("✅ Connected to Oracle DB successfully!")
  conn.close()
  ```

### 3. Wallet Directory Structure ✅
- All required files are present in the wallet directory:
  - cwallet.sso
  - ewallet.p12
  - keystore.jks
  - ojdbc.properties
  - sqlnet.ora
  - tnsnames.ora
  - truststore.jks

### 4. sqlnet.ora Configuration ✅
- The `sqlnet.ora` file has the correct WALLET_LOCATION path:
  ```
  WALLET_LOCATION = (SOURCE = (METHOD = file) (METHOD_DATA = (DIRECTORY=C:\\Users\\aarav\\Desktop\\BRV1\\wallet)))
  SSL_SERVER_DN_MATCH=yes
  ```

### 5. DSN Entry in tnsnames.ora ✅
- The `tnsnames.ora` file contains the correct entries for all DSNs:
  - brvdb1_high
  - brvdb1_low
  - brvdb1_medium
  - brvdb1_tp
  - brvdb1_tpurgent

## Connection Issues

Despite the correct configuration, connection attempts are failing with the error:
```
DPY-6000: Listener refused connection. (Similar to ORA-12506)
```

This error suggests one of the following issues:

1. **Network Connectivity**: There might be network connectivity issues between your machine and the Oracle Cloud database.
   - Check if your network allows outbound connections to port 1522
   - Verify if there are any firewall rules blocking the connection

2. **Oracle Database State**: The Oracle database instance might not be running or available.
   - Check the Oracle Cloud Console to verify that the database is in the "Available" state
   - If the database is stopped, start it from the Oracle Cloud Console

3. **Wallet Configuration**: Although the wallet files are present and correctly configured, they might be outdated or corrupted.
   - Consider downloading a fresh wallet from the Oracle Cloud Console

4. **Authentication Issues**: The username or password might be incorrect.
   - Verify the credentials in the Oracle Cloud Console

## Next Steps

1. **Check Oracle Cloud Console**: Verify that the database instance is running and in the "Available" state.

2. **Network Diagnostics**: Run a simple network test to check connectivity to the Oracle database:
   ```
   ping adb.ap-mumbai-1.oraclecloud.com
   ```

3. **Download Fresh Wallet**: If possible, download a fresh wallet from the Oracle Cloud Console and replace the existing wallet files.

4. **Contact Oracle Support**: If the issue persists, contact Oracle Support for assistance with the connection issues.