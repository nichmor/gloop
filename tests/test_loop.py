import pytest

def test_close(gloop):
    assert not gloop.is_closed()
    gloop.close()
    assert gloop.is_closed()

    gloop.close()
    gloop.close()

    f = gloop.create_future()
    with pytest.raises(RuntimeError):
        gloop.run_forever()
    
    with pytest.raises(RuntimeError):
        gloop.run_until_complete(f)
    