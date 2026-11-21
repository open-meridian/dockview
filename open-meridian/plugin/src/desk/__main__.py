"""Runs the plugin: its reporting role class on the sidecar it is launched
beside, and its page. Everything it reads goes through that sidecar."""

import logging

import meridian

from .book import Book
from .declaration import DECLARATION, PORT
from .pages import pages, use


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    book = Book()
    use(book)
    meridian.run(declaration=DECLARATION, roles=[book], pages=pages, port=PORT)


if __name__ == "__main__":
    main()
