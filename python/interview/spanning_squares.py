

def spanning_squares(r: int, c: int) -> int:

    if r < 1 or c < 1:
        raise ValueError(f"Unexpected inputs - r:{r} c:{c}")
    if r == c:
        return 1
    
    if r > c:
        return 1 + spanning_squares(r - c, c)
    else:
        return 1 + spanning_squares(r, c - r)


def test_spanning_squares(r: int, c: int, expected: int):
    actual = spanning_squares(r, c)
    print(f"spanning_squares({r}, {c}) = {actual}")
    assert actual == expected


def main():
    test_spanning_squares(2, 3, 3)
    test_spanning_squares(3, 3, 1)
    test_spanning_squares(3, 4, 4)
    test_spanning_squares(3, 5, 4)
    test_spanning_squares(4, 5, 5)
    test_spanning_squares(3, 7, 5)
    test_spanning_squares(4, 7, 5)
    test_spanning_squares(2, 3, 3)


if __name__ == "__main__":
    main()