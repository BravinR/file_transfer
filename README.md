# File Transfer

## Test

### Run:

```bash
python proxy.py
```

You should see:

```
Proxy listening on 127.0.0.1:3128
```

### Then from Windows:

```bash
curl.exe -x http://127.0.0.1:3128 https://example.com
```

You should get the response from example.com.
