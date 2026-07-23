#!/bin/sh

set -eu

network_name=${CHATRAW_MODULE_NETWORK:-chatraw-modules}
network_cidr=${CHATRAW_MODULE_NETWORK_CIDR:-172.30.0.0/24}

case "$network_name" in
    ""|*[!A-Za-z0-9_.-]*)
        echo "Invalid CHATRAW_MODULE_NETWORK: $network_name" >&2
        exit 2
        ;;
esac

python_bin=${PYTHON_BIN:-python3}
"$python_bin" -c \
    "import ipaddress,sys; network=ipaddress.ip_network(sys.argv[1], strict=True); assert network.version == 4" \
    "$network_cidr"

if docker network inspect "$network_name" >/dev/null 2>&1; then
    existing_cidr=$(
        docker network inspect \
            --format '{{range .IPAM.Config}}{{println .Subnet}}{{end}}' \
            "$network_name" |
        sed -n '1p'
    )
    if [ "$existing_cidr" != "$network_cidr" ]; then
        echo "Docker network $network_name already exists with subnet $existing_cidr; expected $network_cidr." >&2
        echo "Choose a different CHATRAW_MODULE_NETWORK or set CHATRAW_MODULE_NETWORK_CIDR to the existing subnet." >&2
        exit 1
    fi
    echo "Docker network $network_name already exists with expected subnet $network_cidr"
    exit 0
fi

docker network create \
    --driver bridge \
    --subnet "$network_cidr" \
    "$network_name" >/dev/null
echo "Created Docker network $network_name with subnet $network_cidr"
