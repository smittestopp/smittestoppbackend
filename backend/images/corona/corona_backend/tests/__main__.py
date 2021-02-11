if __name__ == "__main__":
    import pytest
    from tornado.log import enable_pretty_logging

    enable_pretty_logging()
    pytest.main()
