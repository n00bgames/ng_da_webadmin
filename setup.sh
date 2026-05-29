#!/bin/bash

echo
echo "==========================================="
echo " Dune Web Admin Initial Setup"
echo "==========================================="
echo

read -p "Linux username running the web admin: " WEBADMIN_USER

if [ -z "$WEBADMIN_USER" ]; then
echo "No username supplied."
exit 1
fi

if ! id "$WEBADMIN_USER" >/dev/null 2>&1; then
echo "User '$WEBADMIN_USER' does not exist."
exit 1
fi

SUDOERS_FILE="/etc/sudoers.d/dune-web-admin"

echo
echo "Creating sudoers entry for:"
echo "  $WEBADMIN_USER"
echo

sudo tee "$SUDOERS_FILE" >/dev/null <<EOF
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/apt
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/apt-get
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/curl
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/git
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/docker
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/docker-compose
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/libexec/docker/cli-plugins/docker-compose
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/bin/systemctl
${WEBADMIN_USER} ALL=(ALL) NOPASSWD: /usr/sbin/usermod
EOF

sudo chmod 440 "$SUDOERS_FILE"

echo
echo "Validating sudoers configuration..."
sudo visudo -c

if [ $? -ne 0 ]; then
echo
echo "ERROR: sudoers validation failed."
exit 1
fi

echo
echo "Installed:"
echo "  $SUDOERS_FILE"

echo
echo "Testing permissions..."

sudo -n apt --version >/dev/null && echo "✓ apt OK"
sudo -n docker version >/dev/null 2>&1 && echo "✓ docker OK"

echo
echo "Setup complete."
echo
echo "You may need to log out and back in after Docker group changes."
echo
