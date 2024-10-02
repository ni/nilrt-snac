#!/bin/bash -eEu

# Prerequisites:
# - Local Linux box connected to NILRT DUT through two network interfaces
# - IPv6 enabled on both
#
# Usage: remote-test-firewall.sh <LOCAL_SECONDARY_IF> <REMOTE_PRIMARY_ADDR> <REMOTE_SECONDARY_IF>
#
# <LOCAL_SECONDARY_IF>: local ifname of second connection to DUT
# <REMOTE_PRIMARY_ADDR>: DUT's nominal (primary) IP address; ssh'd into
# <REMOTE_SECONDARY_IF>: ifname on DUT of second connection to local

LOCAL_SECONDARY_IF=$1
REMOTE_PRIMARY_ADDR=$2
REMOTE_SECONDARY_IF=$3

REMOTE_USER=root
SOCAT_TIMEOUT=10

TIMEFORMAT="= TIME: %Rs"

# Runs the specified command on the remote system.
do_ssh () {
	local -a opts=() cmds=()
	for x in "$@"; do
		shift
		if [[ $x == -- ]]; then
			opts=( "${cmds[@]}" )
			cmds=( "$@" )
			break
		fi
		cmds+=( "$x" )
	done
	ssh -o ControlPath=/tmp/remotetest.$$ "${opts[@]}" $REMOTE_USER@$REMOTE_PRIMARY_ADDR "${cmds[@]}"
}

# Spawns SSH master session as background job; sets up EXIT handler to kill
# session on exit. Must call this before calling do_ssh yourself.
init_ssh () {
	do_ssh -MNn -- &
	SSH_PID=$!
	trap "do_ssh -O exit -- ; firewall-cmd --reload" EXIT
}


# Reads presumed `ip addr show dev DEV` output from stdin. For each IPv4/IPv6
# address parsed, writes one of the following to stdout:
#
# (ip4|ip6) <tab> (global|link) <tab> ADDRESS <tab> PREFIX
scan_netconfig () {
	local scope
	# TODO: probably doesn't work with ipv6 supersedure
	while read -r line; do
		scope=
		[[ $line =~ scope\ ([^ ]+) ]] && scope=${BASH_REMATCH[1]}
		if [[ $line =~ inet\ ([0-9.]+)/([0-9]+) ]]; then
			printf 'ip4\t%s\t%s\t%s\n' $scope ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}
		elif [[ $line =~ inet6\ ([0-9a-f:]+)/([0-9]+) ]]; then
			printf 'ip6\t%s\t%s\t%s\n' $scope ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}
		fi
	done
}

# Wrapper for running `ip addr show dev $1` on local machine.
get_local_netconfig () {
	local netif=$1 # $LOCAL_SECONDARY_IF
	ip addr show dev $netif
}

# Wrapper for running `ip addr show dev $1` on remote machine.
get_remote_netconfig () {
	local netif=$1 # $REMOTE_SECONDARY_IF
	do_ssh "ip addr show dev $netif"
}

log_section () {
	printf '===\n'
	printf '=== %s\n' "$@"
	printf '===\n'
}

log_testcase () {
	printf '= TEST: %s\n' "$1"
}

log_testcmp () {
	local expected="$1" actual="$2"
	if [[ $expected == $actual ]]; then
		printf '= RESULT: PASS\n'
	else
		printf '= RESULT: FAIL\n'
	fi
}

log_testcmd () {
	local result=0
	log_testcase "$1"
	shift
	eval time "$@" || result=1
	log_testcmp 0 $result
}

log_testcmd_xfail () {
	local result=0
	log_testcase "$1"
	shift
	eval time "$@" || result=1
	log_testcmp 1 $result
}

log_testcmd_exitcode () {
	log_testcase "$1"
	shift
	local expected="$1"
	shift
	local result=0
	eval time "$@" || result=$?
	log_testcmp $expected $result
}

log_section "Reading local secondary IP addresses"

while read -r proto scope addr prefix; do
	case ${proto}-${scope} in
		ip4-global) LOCAL_SECONDARY_IP4_ADDR=$addr ;;
		ip4-link)   LOCAL_SECONDARY_IP4_LINKADDR=$addr ;;
		ip6-global) LOCAL_SECONDARY_IP6_ADDR=$addr ;;
		ip6-link)   LOCAL_SECONDARY_IP6_LINKADDR=$addr ;;
	esac
done < <(get_local_netconfig $LOCAL_SECONDARY_IF | scan_netconfig)

# N.B. ping does not accept bracketed IPv6 addresses, but socat requires them.

# Link-scoped IPv6 addresses are different on different hosts because the zones
# are different.
if [[ -v LOCAL_SECONDARY_IP6_LINKADDR ]]; then
	LOCAL_SECONDARY_IP6_LINKADDR_REMOTE=${LOCAL_SECONDARY_IP6_LINKADDR}%${REMOTE_SECONDARY_IF}
	LOCAL_SECONDARY_IP6_LINKADDR_LOCAL=${LOCAL_SECONDARY_IP6_LINKADDR}%${LOCAL_SECONDARY_IF}
fi

# If a global-scope IPv6 address exists, we use that. Otherwise, we use a link-scoped address.
if ! [[ -v LOCAL_SECONDARY_IP4_ADDR ]]; then
	if ! [[ -v LOCAL_SECONDARY_IP4_LINKADDR ]]; then
		echo "ERROR: Unable to locate any local IPv4 address whatsoever. Exiting." >&2
		exit 1
	fi
	echo "No local secondary IPv4 address found; substituting link-local address."
	LOCAL_SECONDARY_IP4_ADDR=$LOCAL_SECONDARY_IP4_LINKADDR
fi

if ! [[ -v LOCAL_SECONDARY_IP6_ADDR ]]; then
	if ! [[ -v LOCAL_SECONDARY_IP6_LINKADDR ]]; then
		echo "ERROR: Unable to locate any IPv6 address whatsoever. Exiting." >&2
		exit 1
	fi
	echo "No local secondary IPv6 address found; substituting link-local address."
	LOCAL_SECONDARY_IP6_ADDR=$LOCAL_SECONDARY_IP6_LINKADDR
	LOCAL_SECONDARY_IP6_ADDR_REMOTE=$LOCAL_SECONDARY_IP6_LINKADDR_REMOTE
	LOCAL_SECONDARY_IP6_ADDR_LOCAL=$LOCAL_SECONDARY_IP6_LINKADDR_LOCAL
else
	LOCAL_SECONDARY_IP6_ADDR_REMOTE=$LOCAL_SECONDARY_IP6_ADDR
	LOCAL_SECONDARY_IP6_ADDR_LOCAL=$LOCAL_SECONDARY_IP6_ADDR
fi

echo "local ipv4: $LOCAL_SECONDARY_IP4_ADDR"
echo "local ipv6: $LOCAL_SECONDARY_IP6_ADDR_LOCAL $LOCAL_SECONDARY_IP6_ADDR_REMOTE"

# We've never touched the remote system until this point.

log_section "Testing remote primary address connectivity"
log_testcmd "ping4 remote primary" ping -nq -c1 -w1 $REMOTE_PRIMARY_ADDR

log_section "Opening SSH master connection"
init_ssh

log_section "Reading remote secondary IP addresses"
while read -r proto scope addr prefix; do
	case ${proto}-${scope} in
		ip4-global) REMOTE_SECONDARY_IP4_ADDR=$addr ;;
		ip4-link)   REMOTE_SECONDARY_IP4_LINKADDR=$addr ;;
		ip6-global) REMOTE_SECONDARY_IP6_ADDR=$addr ;;
		ip6-link)   REMOTE_SECONDARY_IP6_LINKADDR=$addr ;;
	esac
done < <(get_remote_netconfig $REMOTE_SECONDARY_IF | scan_netconfig)

if [[ -v REMOTE_SECONDARY_IP6_LINKADDR ]]; then
	REMOTE_SECONDARY_IP6_LINKADDR_REMOTE=${REMOTE_SECONDARY_IP6_LINKADDR}%${REMOTE_SECONDARY_IF}
	REMOTE_SECONDARY_IP6_LINKADDR_LOCAL=${REMOTE_SECONDARY_IP6_LINKADDR}%${LOCAL_SECONDARY_IF}
fi

if ! [[ -v REMOTE_SECONDARY_IP4_ADDR ]]; then
	if ! [[ -v REMOTE_SECONDARY_IP4_LINKADDR ]]; then
		echo "ERROR: Unable to locate any remote IPv4 address whatsoever. Exiting." >&2
		exit 1
	fi
	echo "No remote secondary IPv4 address found; substituting link-remote address."
	REMOTE_SECONDARY_IP4_ADDR=$REMOTE_SECONDARY_IP4_LINKADDR
fi

if ! [[ -v REMOTE_SECONDARY_IP6_ADDR ]]; then
	if ! [[ -v REMOTE_SECONDARY_IP6_LINKADDR ]]; then
		echo "ERROR: Unable to locate any IPv6 address whatsoever. Exiting." >&2
		exit 1
	fi
	echo "No remote secondary IPv6 address found; substituting link-remote address."
	REMOTE_SECONDARY_IP6_ADDR=$REMOTE_SECONDARY_IP6_LINKADDR
	REMOTE_SECONDARY_IP6_ADDR_REMOTE=$REMOTE_SECONDARY_IP6_LINKADDR_REMOTE
	REMOTE_SECONDARY_IP6_ADDR_LOCAL=$REMOTE_SECONDARY_IP6_LINKADDR_LOCAL
else
	REMOTE_SECONDARY_IP6_ADDR_REMOTE=$REMOTE_SECONDARY_IP6_ADDR
	REMOTE_SECONDARY_IP6_ADDR_LOCAL=$REMOTE_SECONDARY_IP6_ADDR
fi

echo "remote ipv4: $REMOTE_SECONDARY_IP4_ADDR"
echo "remote ipv6: $REMOTE_SECONDARY_IP6_ADDR_LOCAL $REMOTE_SECONDARY_IP6_ADDR_REMOTE"

log_section "Installing prerequisites"
do_ssh "opkg install socat"

log_section "Resetting firewall configuration"
do_ssh "firewall-cmd --reload"


# These pings can fail, yet later tests can succeed, if the firewall ICMP
# configuration is wonky

log_testcmd "ping IPv4 secondary remote from local" \
	    ping -nq -c1 -w1 $REMOTE_SECONDARY_IP4_ADDR
log_testcmd "ping IPv4 secondary local from remote" \
	    do_ssh "ping -nq -c1 -w1 $LOCAL_SECONDARY_IP4_ADDR"
log_testcmd "ping IPv6 secondary remote from local" \
	    ping -nq -c1 -w1 ${REMOTE_SECONDARY_IP6_ADDR_LOCAL}
log_testcmd "ping IPv6 secondary local from remote" \
	    do_ssh "ping -nq -c1 -w1 ${LOCAL_SECONDARY_IP6_ADDR_REMOTE}"

# Given the protocol specified in $1, what is the appropriate file under
# /proc/net/ to search for bound sockets?
netfile_for_proto () {
	case $1 in
		TCP4) printf tcp ;;
		TCP6) printf tcp6 ;;
		UDP4) printf udp ;;
		UDP6) printf udp6 ;;
	esac
}

# Given the protocol specified in $1, what is the appropriate address type to
# supply to socat when sending data?
socat_sendmode_for_proto () {
	case $1 in
		TCP4) printf TCP4 ;;
		TCP6) printf TCP6 ;;
		UDP4) printf UDP4-SENDTO ;;
		UDP6) printf UDP6-SENDTO ;;
	esac
}

# Construct a complete socat address specification for receiving data.
socat_recvarg () {
	local proto=$1 port=$2 addr=$3

	case $proto in
		TCP4) printf TCP4-LISTEN ;;
		TCP6) printf TCP6-LISTEN ;;
		UDP4) printf UDP4-RECVFROM ;;
		UDP6) printf UDP6-RECVFROM ;;
	esac

	printf ":%d," "$port"

	# socat bind= does not handle IPv6 zones, so we need to explicitly peel
	# off the zone and shove it into so-bindtodevice
	if [[ $addr =~ \[([^%]+)%([^%]+)\] ]]; then
		printf "bind=[%s],so-bindtodevice=%s" ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}
	else
		printf "bind=$addr"
	fi
}

# Wait until the specified port under the specified protocol is bound on the
# local system.
checkforopenport_local () {
	local proto=$1 port=$2
	local netfile=$(netfile_for_proto $proto)
	local i=0
	local portre=":$(printf %04X $port) 0\+:0000"
	while ! grep -q "$portre" /proc/net/$netfile; do
		(( i++ > 50 )) && { echo 'timed out waiting for bind' >&2; return 1; }
		sleep 0.1
	done
}

# Wait until the specified port under the specified protocol is bound on the
# remote system.
checkforopenport_remote () {
	local netfile=$(netfile_for_proto $proto)
	local portre=":$(printf %04X $port) 0\+:0000"
	do_ssh "i=0; while ! grep -q '$portre' /proc/net/$netfile; do (( i++ > 50 )) && { echo 'timed out waiting for bind' >&2; exit 1; }; sleep 0.1; done"
}

# Send a packet from the remote system to the local system over the specified
# protocol and port. localaddr and remoteaddr both specify the same thing (the
# local listening address); localaddr is used on the local system and remoteaddr
# on the remote system; they're different if the address is IPv6 link-local.
test_remotetolocal () {
	local proto=$1 port=$2 localaddr=$3 remoteaddr=$4
	local EXPECTED="$RANDOM"
	val=$(
		timeout $SOCAT_TIMEOUT socat -u $(socat_recvarg $proto $port $localaddr) \
			- </dev/null &
		PID=$!
		trap "kill $PID" EXIT

		checkforopenport_local $proto $port || exit 1
		do_ssh "echo -n $EXPECTED | timeout $SOCAT_TIMEOUT socat -u STDIN $(socat_sendmode_for_proto $proto):$remoteaddr:$port >/dev/null" || exit
		wait $PID
		trap - EXIT
	   )
	[[ $val == $EXPECTED ]]
}

# Send a packet from the local system to the remote system over the specified
# protocol and port. localaddr and remoteaddr both specify the same thing (the
# remote listening address); localaddr is used on the local system and remoteaddr
# on the remote system; they're different if the address is IPv6 link-local.
test_localtoremote () {
	local proto=$1 port=$2 localaddr=$3 remoteaddr=$4
	local EXPECTED="$RANDOM"
	val=$(
		# Lotta magic in this one line. Run this in the background so
		# that we can send I/O to it from a foreground job. If the send
		# operation fails, we need to kill this server; the only way to
		# do this is to force pty allocation with -t so that SIGINT sent
		# to ssh will be re-sent to the remote socat; we must use -tt
		# because the local stdin is not a terminal (because we're
		# running in the background). Run this under exec so that the
		# SIGINT is delivered directly to ssh, not its parent shell,
		# because that shell won't possess its own process group, etc.
		# (because, again, background).
		exec ssh $REMOTE_USER@$REMOTE_PRIMARY_ADDR -tt -- \
		     "timeout $SOCAT_TIMEOUT socat -u $(socat_recvarg $proto $port $remoteaddr) -" &
		PID=$!
		trap "kill -- $PID" EXIT

		checkforopenport_remote $proto $port || exit 1

		echo -n $EXPECTED | \
			socat -u STDIN \
			     $(socat_sendmode_for_proto $proto):$localaddr:$port \
			     >/dev/null || exit 1
		wait $PID
		trap - EXIT
	   )
	[[ $val == $EXPECTED ]]
}

log_testcmd "firewalld is running" do_ssh "firewall-cmd --state"

log_testcmd_xfail "remote to local TCP4 port 12345, blocked" \
	    test_remotetolocal TCP4 12345 \
	    $LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
log_testcmd_xfail "remote to local TCP6 port 12345, blocked" \
	    test_remotetolocal TCP6 12345 \
	    [$LOCAL_SECONDARY_IP6_ADDR_LOCAL] [$LOCAL_SECONDARY_IP6_ADDR_REMOTE]

do_ssh "firewall-cmd --policy=public-out --add-port=12345/tcp"
log_testcmd "remote to local TCP4 port 12345, unblocked" \
	    test_remotetolocal TCP4 12345 \
	    $LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
log_testcmd "remote to local TCP6 port 12345, unblocked" \
	    test_remotetolocal TCP6 12345 \
	    [$LOCAL_SECONDARY_IP6_ADDR_LOCAL] [$LOCAL_SECONDARY_IP6_ADDR_REMOTE]
do_ssh "firewall-cmd --policy=public-out --remove-port=12345/tcp"

log_testcmd_xfail "local to remote TCP4 port 12345, blocked" \
	    test_localtoremote TCP4 12345 \
	    $REMOTE_SECONDARY_IP4_ADDR $REMOTE_SECONDARY_IP4_ADDR
log_testcmd_xfail "local to remote TCP6 port 12345, blocked" \
	    test_localtoremote TCP6 12345 \
	    [$REMOTE_SECONDARY_IP6_ADDR_LOCAL] [$REMOTE_SECONDARY_IP6_ADDR_REMOTE]

do_ssh "firewall-cmd --policy=public-in --add-port=12345/tcp"
log_testcmd "local to remote TCP4 port 12345, unblocked" \
	    test_localtoremote TCP4 12345 \
	    $REMOTE_SECONDARY_IP4_ADDR $REMOTE_SECONDARY_IP4_ADDR
log_testcmd "local to remote TCP6 port 12345, unblocked" \
	    test_localtoremote TCP6 12345 \
	    [$REMOTE_SECONDARY_IP6_ADDR_LOCAL] [$REMOTE_SECONDARY_IP6_ADDR_REMOTE]
do_ssh "firewall-cmd --policy=public-in --remove-port=12345/tcp"



log_testcmd_xfail "remote to local UDP4 port 12345, blocked" \
	    test_remotetolocal UDP4 12345 \
	    $LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
log_testcmd_xfail "remote to local UDP6 port 12345, blocked" \
	    test_remotetolocal UDP6 12345 \
	    [$LOCAL_SECONDARY_IP6_ADDR_LOCAL] [$LOCAL_SECONDARY_IP6_ADDR_REMOTE]

do_ssh "firewall-cmd --policy=public-out --add-port=12345/udp"
log_testcmd "remote to local UDP4 port 12345, unblocked" \
	    test_remotetolocal UDP4 12345 \
	    $LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
log_testcmd "remote to local UDP6 port 12345, unblocked" \
	    test_remotetolocal UDP6 12345 \
	    [$LOCAL_SECONDARY_IP6_ADDR_LOCAL] [$LOCAL_SECONDARY_IP6_ADDR_REMOTE]
do_ssh "firewall-cmd --policy=public-out --remove-port=12345/udp"

log_testcmd_xfail "local to remote UDP4 port 12345, blocked" \
	    test_localtoremote UDP4 12345 \
	    $REMOTE_SECONDARY_IP4_ADDR $REMOTE_SECONDARY_IP4_ADDR
log_testcmd_xfail "local to remote UDP6 port 12345, blocked" \
	    test_localtoremote UDP6 12345 \
	    [$REMOTE_SECONDARY_IP6_ADDR_LOCAL] [$REMOTE_SECONDARY_IP6_ADDR_REMOTE]

do_ssh "firewall-cmd --policy=public-in --add-port=12345/udp"
log_testcmd "local to remote UDP4 port 12345, unblocked" \
	    test_localtoremote UDP4 12345 \
	    $REMOTE_SECONDARY_IP4_ADDR $REMOTE_SECONDARY_IP4_ADDR
log_testcmd "local to remote UDP6 port 12345, unblocked" \
	    test_localtoremote UDP6 12345 \
	    [$REMOTE_SECONDARY_IP6_ADDR_LOCAL] [$REMOTE_SECONDARY_IP6_ADDR_REMOTE]
do_ssh "firewall-cmd --policy=public-in --remove-port=12345/udp"

test_nofirewall () {
	do_ssh "/etc/init.d/firewalld stop"
	trap "do_ssh '/etc/init.d/firewalld start'" RETURN
	log_testcmd_exitcode do_ssh 252 "firewall-cmd --state"

	log_testcmd "remote to local TCP4 port 12345, blocked, firewalld not running" \
		test_remotetolocal TCP4 12345 \
		$LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
	do_ssh "/etc/init.d/firewalld start"
	trap - RETURN
}
test_nofirewall

do_ssh "firewall-cmd --permanent --policy=public-out --set-target=ACCEPT && firewall-cmd --reload"
log_testcmd "remote to local TCP4 port 12345, blocked, firewalld not running" \
	test_remotetolocal TCP4 12345 \
	$LOCAL_SECONDARY_IP4_ADDR $LOCAL_SECONDARY_IP4_ADDR
do_ssh "firewall-cmd --permanent --policy=public-out --set-target=REJECT && firewall-cmd --reload"
