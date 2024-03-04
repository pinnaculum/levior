from IPy import IP

from levior.request import ipaddr_allowed


class TestIPFilter:
    def test_ipaddr(self):
        localip = IP('127.0.0.1')

        assert ipaddr_allowed(localip, [IP('127.0.0.0/24')]) is True
        assert ipaddr_allowed(localip, [
            IP('127.0.0.4/32'),
            IP('::1')
        ]) is False
        assert ipaddr_allowed(localip, []) is False
