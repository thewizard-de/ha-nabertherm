# Reproducing the traffic capture

How the MyNabertherm cloud API was reverse-engineered, so the control test (start/stop with the
furnace **online**) can be redone later. The app is Flutter (`libflutter.so`, `libapp.so`);
the business logic is compiled Dart in `libapp.so`.

> Captured flows contain a live JWT — keep them private, never commit them.

## Why it is hard

1. **Cert pinning.** BoringSSL pinning lives inside `libflutter.so` (symbols stripped).
2. **Proxy bypass.** The HTTP client (`dio`, `dart:io`) ignores the Android system proxy, so a
   normal MITM proxy sees nothing.

## Environment

- Emulator `naber-root` (x86_64, Android 14, rooted, `-writable-system`), system CA installed.
- **frida-server 16.6.6** — not 17.x, whose agent crashes (SIGSEGV) on this image. Use a matching
  frida Python in a venv.
- SELinux permissive (`setenforce 0`).

## Defeat the pinning

Patch `ssl_verify_peer_cert` by offset instead of symbol:

- `libflutter.so + 0x7d524a` → `Interceptor.replace(..., NativeCallback(() => 0))` (return 0).
- Use **fresh-attach**, not spawn: a spawn session cannot see the `libflutter` loaded from the
  APK because of linker-namespace isolation.

Reach frida over TCP (USB backend is flaky): `adb forward tcp:27042 tcp:27042`, then
`frida.add_remote_device("127.0.0.1:27042")`.

## Defeat the proxy bypass

Because `dio` ignores the system proxy, redirect the backend IPs with **iptables DNAT** to local
mitmproxy reverse proxies:

```
mitmdump --mode reverse:https://<backend-ip> -p <port> --set keep_host_header=true --ssl-insecure
```

DNAT the backend IP (resolve `www.get-entangled.de`) to the reverse-proxy port. `keep_host_header`
preserves the original Host so TLS SNI/vhost routing still works.

## Reading the result

The snapshot and login flows then appear in the mitmproxy flow files in cleartext. Map the
parameters against [API.md](API.md).

## For the control test

Bring the furnace online, run the capture as above, and press start/stop in the app. If a
write/control request appears, document the method, path and body in API.md. So far only
`POST /Account/Login` is a POST; everything else is GET.
