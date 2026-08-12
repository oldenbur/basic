"""
  You operate a consulting service with a single specialist. Clients submit booking requests in advance, each with a start time, end time, and the revenue it
  would generate. The specialist can only handle one booking at a time, and bookings cannot overlap. Your goal is to select a subset of non-overlapping
  bookings that maximizes total revenue.                                                                                                                     
                  
  Write a function:

  max_revenue(bookings: list of (start, end, revenue)) -> int

  Constraints:
  - start and end are integers where start < end
  - revenue > 0
  - A booking ending at time t does not conflict with a booking starting at time t
  - 0 ≤ len(bookings) ≤ 10,000

  Examples:

  Input:  [(1, 3, 50), (2, 5, 80), (4, 7, 60), (6, 8, 70)]
  Output: 130
  Explanation: Select (1,3,50) and (4,7,60) and... wait —
    (1,3,50) + (4,7,60) = 110, but (2,5,80) + (6,8,70) = 150.
    Output: 150

  Input:  [(1, 2, 10), (2, 3, 20), (3, 4, 30)]
  Output: 60  (all three, they don't overlap)

  Input:  [(1, 10, 100)]
  Output: 100

"""

from typing import TypeAlias
import bisect


Booking: TypeAlias = tuple[int, int, int]


def max_bookings_recursive(input: list[Booking]) -> list[Booking]:

    by_end = sorted(input, key=lambda booking: booking[1])

    return extend(0, [], by_end)

    
def extend(cur: int, bookings: list[Booking], by_end: list[Booking]) -> list[Booking]:

    if cur >= len(by_end):
        return bookings

    bookings_end = [booking[1] for booking in bookings]
    cur_i = bisect.bisect_left(bookings_end, by_end[cur][0])
    bookings_with = bookings[:cur_i] + [by_end[cur]] if cur_i != 0 else [by_end[cur]]
    
    result_with = extend(cur + 1, bookings_with, by_end)
    result_without = extend(cur + 1, bookings, by_end)

    print(f"cur: {cur} - bookings: {bookings}  result_with: {result_with}  result_without: {result_without}")

    if revenue(result_with) > revenue(result_without):
        return result_with
    else:
        return result_without


def revenue(bookings: list[Booking]) -> int:
    return 0 if not bookings else sum([booking[2] for booking in bookings])


def max_bookings_dp(bookings: list[Booking]) -> int:

    if len(bookings) < 1:
        return 0

    by_end = sorted(bookings, key=lambda booking: booking[1])
    bookings_end = [b[1] for b in by_end]

    revenue: list[int] = []
    for i, booking in enumerate(by_end):
        if i == 0:
            revenue.append(booking[2])
            continue

        i_replace = bisect.bisect_right(bookings_end, by_end[i][0])
        
        prev_revenue = 0 if i_replace == 0 else revenue[i_replace - 1]
        revenue.append(max(prev_revenue + booking[2], revenue[i-1]))
    
    return revenue[-1]


def main():
    # input1 = [(1, 3, 50), (2, 5, 80)]
    # actual1 = max_bookings(input1)
    # assert actual1 == [(2, 5, 80)]

    input2 = [(2, 5, 80), (4, 7, 60), (6, 8, 70), (1, 3, 50)]
    actual2 = max_bookings_dp(input2)
    assert actual2 == 150

    print("SUCCESS")

if __name__ == "__main__":
    main()