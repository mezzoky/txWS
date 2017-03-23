# -*- coding: utf-8 -*-

from twisted.python import log
from twisted.internet import reactor
from twisted.internet.protocol import Protocol, Factory
from twisted.protocols.policies import ProtocolWrapper

import six
from txws import (
    WebSocketFactory, WebSocketProtocol, RFC6455, HYBI10, HYBI07, HYBI00,
    make_hybi07_frame, parse_hybi00_frames, parse_hybi07_frames,
    WSException, NORMAL, CLOSE, decoders, PONG,
)
from sys import stdout
from twisted.application.strports import listen
log.startLogging(stdout)


PING_CODE = 'PI'
PONG_CODE = 'PO'


class Wrapper(WebSocketProtocol):
    def __init__(self, *args, **kwargs):
        WebSocketProtocol.__init__(self, *args, **kwargs)
        self.setBinaryMode(True)

    def write(self, data):
        print 'write', data, self.flavor
        if data == PING_CODE and self.flavor == RFC6455 and 1:
            return self.ping()
        WebSocketProtocol.write(self, data)

    def ping(self):
        header = chr(0x80 | 0x9)
        end = chr(0)
        ret = six.b(header + end)
        print 'do ping', ret.encode('hex')
        self.transport.write(ret)

    def parseFrames(self):
        """
        Find frames in incoming data and pass them to the underlying protocol.
        """

        if self.flavor == HYBI00:
            parser = parse_hybi00_frames
        elif self.flavor in (HYBI07, HYBI10, RFC6455):
            parser = parse_hybi07_frames
        else:
            raise WSException("Unknown flavor %r" % self.flavor)

        try:
            frames, self.buf = parser(self.buf)
        except WSException as wse:
            # Couldn't parse all the frames, something went wrong, let's bail.
            self.close(wse.args[0])
            return

        for frame in frames:
            opcode, data = frame
            if opcode == NORMAL:
                # Business as usual. Decode the frame, if we have a decoder.
                if self.codec:
                    data = decoders[self.codec](data)
                # Pass the frame to the underlying protocol.
                ProtocolWrapper.dataReceived(self, data)
            elif opcode == PONG:
                ProtocolWrapper.dataReceived(self, PONG_CODE)
            elif opcode == CLOSE:
                # The other side wants us to close. I wonder why?
                reason, text = data
                log.msg("Closing connection: %r (%d)" % (text, reason))

                # Close the connection.
                self.close()


class WSFactory(WebSocketFactory):
    protocol = Wrapper


class EchoProtocol(Protocol):
    def dataReceived(self, data):
        print 'echo data receive', data

    def makeConnection(self, transport):
        Protocol.makeConnection(self, transport)
        self.ping()

    def ping(self):
        self.transport.write(PING_CODE)
        reactor.callLater(3, self.ping)


class EchoFactory(Factory):
    protocol = EchoProtocol


port = listen("tcp:5600", WSFactory(EchoFactory()))

reactor.run()
