transmission-opnsense-nat-pmp-relay
===================================

Daemon facilitating NAT-PMP in an OPNSense and Transmission setup.

This service will:

- Send NAT-PMP requests every 45 seconds to get a port
- Update forwarding rules on OPNSense accordingly
- Update the port on Transmission accordingly

This is tested in a [Wireguard setup with selective routing](https://docs.opnsense.org/manual/how-tos/wireguard-selective-routing.html), but might also work in other cases.


OPNSense Port Forwarding
------------------------

**This section only explains how to setup the port forwarding**

First, assign an IP to your daemon and:

- Allow it to access OPNSense
- Allow it to access Transmission
- Route the rest of the traffic through your VPN

Then, add the port forwarding rules:

- In Firewall -> Aliases, create a new `VPN_Forwarded_Port` alias, set a random port there
- In Firewall -> Nat -> Port Forward, create a new rule with the following settings:
    - **Interface:** the VPN interface
    - **Protocol:** TCP/UDP
    - **Destination:** the VPN interface address
    - **Destination port range:** the `VPN_Forwarded_Port alias`
    - **Redirect target IP:** the IP of your Transmission
    - **Redirect target port:** `VPN_Forwarded_Port`
    - **Filter rule association:** None
- In Firewall -> Rules -> You VPN, create a new rule with the following settings:
    - **Interface:** the VPN interface
    - **Protocol:** TCP/UDP
    - **Destination:** the IP of your Transmission
    - **Destination port range:** VPN_Forwarded_Port
    - **reply-to:** (under "Advanced features") the Gateway of your VPN

See https://github.com/opnsense/core/issues/4389#issuecomment-865349224

Launch the daemon
-----------------

In OPNSense, under System -> Access -> Users create a new user:

- **Username**: `nat-pmp-daemon`
- **Password**: set a random password (you will not need it)
- **Privileges**: `Firewall: Alias: Edit`

Then create an API Key for this user.

To launch the daemon:

```
docker run -d \
  --name nat-pmp-relay \
  --restart on-failure \
  --network your-network \
  --ip 192.168.0.200 \
  -e OPNSENSE_URL=http://your-opnsense-url \
  -e OPNSENSE_KEY=.... \
  -e OPNSENSE_SECRET=... \
  -e OPNSENSE_ALIAS_NAME=VPN_Forwarded_Port \
  -e TRANSMISSION_URL=http://user-password@your-transmission-url/transmission \
  -e NAT_PMP_GATEWAY=10.2.0.1 \
  ugomeda/transmission-opnsense-nat-pmp-relay:latest
```
