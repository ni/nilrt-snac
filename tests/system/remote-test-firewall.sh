#!/bin/bash -eEu

# Usage: remote-test-firewall.sh

readonly DIST="${0%/*}"

SOCAT_TIMEOUT=10

TIMEFORMAT="= TIME: %Rs"

# HOST2_NS is what will actually contain the firewalld instance we are testing
# here. HOST1_NS is created in order to possess a container with no existing
# firewall, so that the current system firewall configuration cannot interfere
# with the tests.
HOST1_NS=firewalltest1
HOST2_NS=firewalltest2

HOST1_IF=veth0a
HOST2_IF=veth0b

# This test cheerfully assumes that 192.168.55.0/24 is not in use, but IPv6
# global addresses are autogenerated using gen_ula.py, which implements ULA
# generation as defined in RFC 4193.
HOST1_IP4=192.168.55.1
HOST2_IP4=192.168.55.2

gen_local_ula () {
	readonly mac="$1"
	$DIST/gen_ula.py --eui48 $mac
}

gen_remote_ula () {
	readonly mac="$1" network="$2"
	$DIST/gen_ula.py --eui48 $mac --network $network
}

mac_for_iface () {
	readonly iface="$1"
	ip link show dev $iface | grep -Eo 'link/ether ..:..:..:..:..:..' | cut -f2 -d\ 
}

mac_for_iface_ns () {
	readonly ns="$1" iface="$2"
	ip netns exec $ns \
	   ip link show dev $iface \
		| grep -Eo 'link/ether ..:..:..:..:..:..' \
		| cut -f2 -d\ 
}

# We are running firewalld inside a network namespace, potentially while another
# instance of firewalld is already running; the two instances should not
# interact with each other. To ensure this, we also spawn our own dbus server,
# with its own config file, and steer firewalld to it by setting
# DBUS_SYSTEM_BUS_ADDRESS.

DBUS_CONF="$DIST/dbus-test.conf"

dbus_pidfile_ns () {
	local NS=$1
	printf '/var/run/dbus-ni-%s.pid' "$NS"
}

dbus_socket_ns () {
	local NS=$1
	printf 'unix:abstract=ni-dbus-socket-%s' "$NS"
}

start_dbus_ns () {
        local NS=$1
	run_cmd ip netns exec $NS \
		dbus-daemon --address=$(dbus_socket_ns $NS) --print-pid \
		--config-file=$DBUS_CONF > $(dbus_pidfile_ns $NS)
}

stop_dbus_ns () {
	local NS=$1
	local PIDFILE=$(dbus_pidfile_ns $NS)
	run_cmd kill $(<$PIDFILE)
	run_cmd rm -f $PIDFILE
}

run_cmd () {
	printf 'CMD:' >&2
	printf ' %q' "$@" >&2
	printf '\n' >&2
	"$@"
}

run_cmd_ns () {
	local NS=$1
	shift
	run_cmd ip netns exec $NS \
		env DBUS_SYSTEM_BUS_ADDRESS=$(dbus_socket_ns $NS) "$@"
}

run_bg () {
	exec "$@" &
	echo "BG ($!): $@" >&2
	ps ax | grep $! >&2
}

run_bg_ns () {
	local NS=$1
	shift
	run_bg ip netns exec $NS \
		env DBUS_SYSTEM_BUS_ADDRESS=$(dbus_socket_ns $NS) "$@"
}

firewalld_pidfile_ns () {
	local NS=$1
	printf '/var/run/firewalld-%s.pid' "$NS"
}

start_firewalld_ns () {
	local NS=$1
	run_bg_ns $NS /usr/sbin/firewalld --log-target=console --nopid --nofork
	#  --debug 5
	run_cmd echo $! > $(firewalld_pidfile_ns $NS)

	# Observed in 2.2 only: need to wait for firewalld to respond to socket requests
	sleep 1
	local i=0
	while ! run_cmd_ns $NS /usr/bin/firewall-cmd --state && (( i++ < 10 )); do
		sleep 1
	done
	if (( i >= 10 )); then
		echo "ERROR: firewalld not started" >&2
		exit 1
	fi
}

stop_firewalld_ns () {
	local NS=$1
	run_cmd kill $(<$(firewalld_pidfile_ns $NS))
}

# Spin up firewalld under test in a network namespace ($HOST2_NS), which talks
# to another spun-up network namespace ($HOST1_NS) over a virtual network
# interface (a veth pair $HOST1_IF/$HOST2_IF).
init_containers () {
	ip netns del $HOST1_NS >&/dev/null ||:
	ip netns del $HOST2_NS >&/dev/null ||:
	ip link delete $HOST1_IF >&/dev/null ||:
	ip link delete $HOST2_IF >&/dev/null ||:

	run_cmd ip netns add $HOST1_NS
	run_cmd ip netns add $HOST2_NS
	run_cmd ip link add $HOST1_IF type veth peer name $HOST2_IF

	local_mac=$(mac_for_iface $HOST1_IF)
	remote_mac=$(mac_for_iface $HOST2_IF)

	run_cmd ip link set $HOST1_IF netns $HOST1_NS
	run_cmd ip link set $HOST2_IF netns $HOST2_NS

	# The address appears to get reset after the ns switch, so that must
	# happen first. Some sources claim that you need to attach a bridge to
	# one side of a veth to send anything across it; that appears to be
	# mistaken.
	run_cmd_ns $HOST1_NS ip link set $HOST1_IF up
	run_cmd_ns $HOST2_NS ip link set $HOST2_IF up
	run_cmd_ns $HOST1_NS ip addr add $HOST1_IP4/24 dev $HOST1_IF
	run_cmd_ns $HOST2_NS ip addr add $HOST2_IP4/24 dev $HOST2_IF

	IFS=/ read -r HOST1_IP6GLOBAL HOST1_IP6PREFIX < \
	   <(gen_local_ula $local_mac)
	IFS=/ read -r HOST2_IP6GLOBAL HOST2_IP6PREFIX < \
	   <(gen_remote_ula $local_mac $HOST1_IP6GLOBAL/$HOST1_IP6PREFIX)
	run_cmd_ns $HOST1_NS ip addr add $HOST1_IP6GLOBAL/$HOST1_IP6PREFIX dev $HOST1_IF
	run_cmd_ns $HOST2_NS ip addr add $HOST2_IP6GLOBAL/$HOST2_IP6PREFIX dev $HOST2_IF

	# TODO: a short sleep appears to be needed for IPv6 connectivity to work
	# right, haven't figured out why yet
	sleep 1

	while read -r proto scope addr prefix; do
		case ${proto}-${scope} in
			ip6-link) HOST1_IP6LINK_ADDR=$addr ;;
		esac
	done < <(run_cmd_ns $HOST1_NS ip addr show dev $HOST1_IF | scan_netconfig)

	# Link-scoped IPv6 addresses are different on different hosts because
	# the zones are different.
	HOST1_IP6LINK_HOST1=${HOST1_IP6LINK_ADDR}%${HOST1_IF}
	HOST1_IP6LINK_HOST2=${HOST1_IP6LINK_ADDR}%${HOST2_IF}

	while read -r proto scope addr prefix; do
		case ${proto}-${scope} in
			ip6-link) HOST2_IP6LINK_ADDR=$addr ;;
		esac
	done < <(run_cmd_ns $HOST2_NS ip addr show dev $HOST2_IF | scan_netconfig)
	HOST2_IP6LINK_HOST1=${HOST2_IP6LINK_ADDR}%${HOST1_IF}
	HOST2_IP6LINK_HOST2=${HOST2_IP6LINK_ADDR}%${HOST2_IF}

	#start_dbus_ns $HOST1_NS
	start_dbus_ns $HOST2_NS
	#start_firewalld_ns $HOST1_NS
	start_firewalld_ns $HOST2_NS

	# TODO: firewalld is not emitting rules for the public zone if there is
	# not an interface assigned to it, even though it's the default zone.
	# Workaround is to explicitly add the if. Observed in 1.3.2; possibly
	# fixed in 2.2???

	run_cmd_ns $HOST2_NS firewall-cmd --zone=public --add-interface=$HOST2_IF

	trap "cleanup_containers" EXIT
}

cleanup_containers () {
	#stop_firewalld_ns $HOST1_NS
	stop_firewalld_ns $HOST2_NS ||:
	#stop_dbus_ns $HOST1_NS
	stop_dbus_ns $HOST2_NS ||:

	run_cmd_ns $HOST1_NS ip link del $HOST1_IF ||:
	run_cmd_ns $HOST2_NS ip link del $HOST2_IF ||:
	run_cmd ip netns delete $HOST1_NS ||:
	run_cmd ip netns delete $HOST2_NS ||:
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
		# Uncomment this to dump into a shell at the point of failure.
		# This is extremely useful for debugging.
		# bash
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
	local expected="$2" result=0
	shift 2
	eval time "$@" || result=$?
	log_testcmp $expected $result
}

init_containers

log_section "Installing prerequisites"
opkg install socat

log_testcmd "ping IPv4 secondary remote from local" \
	    run_cmd_ns $HOST1_NS ping -nq -c1 -w1 $HOST2_IP4
log_testcmd "ping IPv4 secondary local from remote" \
	    run_cmd_ns $HOST2_NS ping -nq -c1 -w1 $HOST1_IP4
log_testcmd "ping IPv6 secondary remote from local" \
	    run_cmd_ns $HOST1_NS ping -nq -c1 -w1 ${HOST2_IP6LINK_HOST1}
log_testcmd "ping IPv6 secondary local from remote" \
	    run_cmd_ns $HOST2_NS ping -nq -c1 -w1 ${HOST1_IP6LINK_HOST2}

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
# local system. This is generally necessary because listening-server startup is
# asynchronous, and socat provides no out-of-band mechanism to signal when it's
# set up listening.
checkforopenport_ns () {
	local ns=$1 proto=$2 port=$3
	local netfile=$(netfile_for_proto $proto)
	local i=0
	local portre=":$(printf %04X $port) 0\+:0000"
	while ! run_cmd_ns $ns grep -q "$portre" /proc/net/$netfile; do
		(( i++ > 50 )) && { echo 'timed out waiting for bind' >&2; return 1; }
		sleep 0.2
	done
}


# Wait until the specified port under the specified protocol is NOT bound on the
# local system. This becomes important when the server on the same
# namespace/proto/port had to be killed. (TODO: But that only matters under
# TIME_WAIT, right? But if so, that means a connection was made. But the traffic
# was blocked, how could the connection have even happened?)
checkforclosedport_ns () {
	local ns=$1 proto=$2 port=$3
	local netfile=$(netfile_for_proto $proto)
	local i=0
	local portre=":$(printf %04X $port) 0\+:0000"
	while run_cmd_ns $ns grep -q "$portre" /proc/net/$netfile; do
		(( i++ > 50 )) && { echo 'timed out waiting for shutdown' >&2; return 1; }
		sleep 0.2
	done
}


# Send a packet from the remote system to the local system over the specified
# protocol and port. localaddr and remoteaddr both specify the same thing (the
# local listening address); localaddr is used on the local system and remoteaddr
# on the remote system; they're different if the address is IPv6 link-local.
test_remotetolocal () {
	local proto=$1 port=$2 localaddr=$3 remoteaddr=$4
	local EXPECTED="$RANDOM"
	local sendret recvret actual
	IFS=$'\t' read -r actual sendret recvret < <(
		checkforclosedport_ns $HOST1_NS $proto $port || exit 1
		printf "'"
		run_cmd_ns $HOST1_NS timeout $SOCAT_TIMEOUT \
			   socat -u $(socat_recvarg $proto $port $localaddr) \
			   - </dev/null &
		PID=$!
		trap "kill $PID" EXIT

		checkforopenport_ns $HOST1_NS $proto $port || exit 1
		sendret=0
		recvret=0
		echo -n $EXPECTED | run_cmd_ns $HOST2_NS timeout $SOCAT_TIMEOUT \
					       socat -u STDIN \
					       $(socat_sendmode_for_proto $proto):$remoteaddr:$port \
					       >/dev/null || sendret=$?
		(( sendret == 0 )) || kill $PID
		wait $PID
		recvret=$?
		printf "'\t%d\t%d\n" $recvret $sendret
		trap - EXIT
	   )
	printf '= EXPECTED: %s\n= ACTUAL: %s\n= SENDRET: %d\n= RECVRET: %d\n' \
	       "'${EXPECTED}'" $actual $sendret $recvret
	[[ $actual == "'${EXPECTED}'" ]]
}

# Send a packet from the local system to the remote system over the specified
# protocol and port. localaddr and remoteaddr both specify the same thing (the
# remote listening address); localaddr is used on the local system and remoteaddr
# on the remote system; they're different if the address is IPv6 link-local.
test_localtoremote () {
	local proto=$1 port=$2 localaddr=$3 remoteaddr=$4
	local EXPECTED="$RANDOM"
	local sendret recvret actual
	IFS=$'\t' read -r actual sendret recvret < <(
		printf "'"
		checkforclosedport_ns $HOST2_NS $proto $port || exit 1

		run_cmd_ns $HOST2_NS timeout $SOCAT_TIMEOUT socat -u \
			   $(socat_recvarg $proto $port $remoteaddr) - &
		PID=$!
		trap "kill -- $PID" EXIT

		checkforopenport_ns $HOST2_NS $proto $port || exit 1

		sendret=0
		recvret=0
		echo -n $EXPECTED | \
			run_cmd_ns $HOST1_NS socat -u STDIN \
			     $(socat_sendmode_for_proto $proto):$localaddr:$port \
			     >/dev/null || sendret=$?
		(( sendret == 0 )) || kill $PID >& /dev/null
		wait $PID
		recvret=$?
		printf "'\t%d\t%d\n" $recvret $sendret
		trap - EXIT
	   )
	printf '= EXPECTED: %s\n= ACTUAL: %s\n= SENDRET: %d\n= RECVRET: %d\n' \
	       "'${EXPECTED}'" $actual $sendret $recvret
	[[ $actual == "'${EXPECTED}'" ]]
}

log_testcmd "firewalld is running" firewall-cmd --state

log_testcmd_xfail "remote to local TCP4 port 12345, blocked" \
	    test_remotetolocal TCP4 12345 \
	    $HOST1_IP4 $HOST1_IP4
log_testcmd_xfail "remote to local TCP6 port 12345, blocked" \
	    test_remotetolocal TCP6 12345 \
	    [$HOST1_IP6LINK_HOST1] [$HOST1_IP6LINK_HOST2]

run_cmd_ns $HOST2_NS firewall-cmd --policy=public-out --add-port=12345/tcp
log_testcmd "remote to local TCP4 port 12345, unblocked" \
	    test_remotetolocal TCP4 12345 \
	    $HOST1_IP4 $HOST1_IP4
log_testcmd "remote to local TCP6 port 12345, unblocked" \
	    test_remotetolocal TCP6 12345 \
	    [$HOST1_IP6LINK_HOST1] [$HOST1_IP6LINK_HOST2]
run_cmd_ns $HOST2_NS firewall-cmd --policy=public-out --remove-port=12345/tcp

log_testcmd_xfail "local to remote TCP4 port 12345, blocked" \
	    test_localtoremote TCP4 12345 \
	    $HOST2_IP4 $HOST2_IP4
log_testcmd_xfail "local to remote TCP6 port 12345, blocked" \
	    test_localtoremote TCP6 12345 \
	    [$HOST2_IP6LINK_HOST1] [$HOST2_IP6LINK_HOST2]

run_cmd_ns $HOST2_NS firewall-cmd --policy=public-in --add-port=12345/tcp
log_testcmd "local to remote TCP4 port 12345, unblocked" \
	    test_localtoremote TCP4 12345 \
	    $HOST2_IP4 $HOST2_IP4
log_testcmd "local to remote TCP6 port 12345, unblocked" \
	    test_localtoremote TCP6 12345 \
	    [$HOST2_IP6LINK_HOST1] [$HOST2_IP6LINK_HOST2]
run_cmd_ns $HOST2_NS firewall-cmd --policy=public-in --remove-port=12345/tcp



log_testcmd_xfail "remote to local UDP4 port 12345, blocked" \
	    test_remotetolocal UDP4 12345 \
	    $HOST1_IP4 $HOST1_IP4
log_testcmd_xfail "remote to local UDP6 port 12345, blocked" \
	    test_remotetolocal UDP6 12345 \
	    [$HOST1_IP6LINK_HOST1] [$HOST1_IP6LINK_HOST2]

run_cmd_ns $HOST2_NS firewall-cmd --policy=public-out --add-port=12345/udp
log_testcmd "remote to local UDP4 port 12345, unblocked" \
	    test_remotetolocal UDP4 12345 \
	    $HOST1_IP4 $HOST1_IP4
log_testcmd "remote to local UDP6 port 12345, unblocked" \
	    test_remotetolocal UDP6 12345 \
	    [$HOST1_IP6LINK_HOST1] [$HOST1_IP6LINK_HOST2]
run_cmd_ns $HOST2_NS firewall-cmd --policy=public-out --remove-port=12345/udp

log_testcmd_xfail "local to remote UDP4 port 12345, blocked" \
	    test_localtoremote UDP4 12345 \
	    $HOST2_IP4 $HOST2_IP4
log_testcmd_xfail "local to remote UDP6 port 12345, blocked" \
	    test_localtoremote UDP6 12345 \
	    [$HOST2_IP6LINK_HOST1] [$HOST2_IP6LINK_HOST2]

run_cmd_ns $HOST2_NS firewall-cmd --policy=public-in --add-port=12345/udp
log_testcmd "local to remote UDP4 port 12345, unblocked" \
	    test_localtoremote UDP4 12345 \
	    $HOST2_IP4 $HOST2_IP4
log_testcmd "local to remote UDP6 port 12345, unblocked" \
	    test_localtoremote UDP6 12345 \
	    [$HOST2_IP6LINK_HOST1] [$HOST2_IP6LINK_HOST2]
run_cmd_ns $HOST2_NS firewall-cmd --policy=public-in --remove-port=12345/udp

test_nofirewall () {
	# run_cmd_ns $HOST2_NS "/etc/init.d/firewalld stop"
	# trap "run_cmd_ns $HOST2_NS '/etc/init.d/firewalld start'" RETURN
	# log_testcmd_exitcode run_cmd_ns $HOST2_NS 252 "firewall-cmd --state"
	stop_firewalld_ns $HOST2_NS
	sleep 1
	log_testcmd_exitcode "firewalld is not running" 252 run_cmd_ns $HOST2_NS firewall-cmd --state

	log_testcmd "remote to local TCP4 port 12345, blocked, firewalld not running" \
		test_remotetolocal TCP4 12345 \
		$HOST1_IP4 $HOST1_IP4
	start_firewalld_ns $HOST2_NS
	# TODO: copy from init, cf comments
	run_cmd_ns $HOST2_NS firewall-cmd --zone=public --add-interface=$HOST2_IF

	trap - RETURN
}
test_nofirewall

run_cmd_ns $HOST2_NS firewall-cmd --permanent --policy=public-out --set-target=ACCEPT && \
	run_cmd_ns $HOST2_NS firewall-cmd --reload
log_testcmd "remote to local TCP4 port 12345, blocked, firewalld not running" \
	test_remotetolocal TCP4 12345 \
	$HOST1_IP4 $HOST1_IP4
run_cmd_ns $HOST2_NS firewall-cmd --permanent --policy=public-out --set-target=REJECT \
	&& run_cmd_ns $HOST2_NS firewall-cmd --reload
