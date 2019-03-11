import tornado.ioloop
import tornado.web
import tornado.websocket


class EchoWebSocket(tornado.websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True

    def data_received(self, chunk):
        pass

    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        print("Receiving message: " + message)
        self.write_message(u"what you whant: " + message)

    def on_close(self):
        print("WebSocket closed")


def make_app():
    return tornado.web.Application([
        (r"/", EchoWebSocket),
    ])


if __name__ == "__main__":
    app = make_app()
    app.listen(8888)
    tornado.ioloop.IOLoop.current().start()
