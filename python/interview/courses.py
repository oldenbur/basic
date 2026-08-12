from dataclasses import dataclass, field
import pytest


@dataclass
class Course:

    course: int
    children: set[int] = field(default_factory=set)
    degree: int = 0


def order_courses(deps: list[list[int]]) -> list[int]:
    """
    Assume that the input is an unordered set of int pairs that represent dependencies between two
    college courses. The function constructs a possible valid ordering of courses, based on their
    dependency structure. If the dependency structure is invalid, the function raises ValueError
    which includes details.
    """

    courses: dict[int, Course] = {}
    heads: set[int] = set() 

    # build the graph
    for cl in deps:

        child: Course = courses.get(cl[0], Course(cl[0]))
        child.degree += 1
        courses[cl[0]] = child
        # heads.discard(cl[0])

        if cl[1] in courses:
            courses[cl[1]].children.add(cl[0])
        else:
            courses[cl[1]] = Course(cl[1], {cl[0]})
            # heads.add(cl[1])

    heads = {c.course for _, c in courses.items() if c.degree == 0}

    if not heads:
        raise ValueError("detected dependency loop")

    order: list[int] = []

    while len(heads) > 0:
        pi = heads.pop()
        if pi not in courses:
            raise ValueError(f"already visited parent course {pi}")
        parent = courses[pi]
        del courses[pi]
        order.append(pi)
        for ci in parent.children:
            if ci not in courses:
                raise ValueError(f"already visited child course {ci}")
            child = courses[ci]
            child.degree -= 1
            if child.degree < 0:
                raise ValueError(f"child {ci} degree unexpectedly sub-zero")
            elif child.degree == 0:
                heads.add(ci)
    
    return order


def main():
    actual1 = order_courses([[1, 0], [2, 0], [3, 1], [3, 2]])
    assert actual1 in [
        [0, 1, 2, 3], [0, 2, 1, 3]
    ]

    actual2 = order_courses([[3, 2], [2, 0], [1, 0], [3, 1]])
    assert actual2 in [
        [0, 1, 2, 3], [0, 2, 1, 3]
    ]

    actual3 = order_courses([[3, 2], [2, 0], [1, 0], [3, 1], [2, 1]])
    assert actual3 == [0, 1, 2, 3]

    with pytest.raises(ValueError):
        order_courses([[2, 1], [1, 0], [0, 2]])

    print("SUCCESS")

if __name__ == "__main__":
    main()
