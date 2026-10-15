#include "practice.h"

#include <cstdio>
#include <vector>
#include <deque>
#include <gtest/gtest.h>

TEST(PracticeTest, ReturnsPracticeValue) {
    EXPECT_EQ(intvw::practice_value(), 42);
}

namespace {

class LRUCacheTest : public ::testing::Test {
protected:
    intvw::LRUCache cache_{3};
};

struct Person {
    const char* name;
    int age;
};

TEST_F(LRUCacheTest, GetMiddleTailAfterPopulate) {
    cache_.put(1, 100);
    cache_.put(2, 200);
    cache_.put(3, 300);
    
    EXPECT_EQ(cache_.get(1), 100);
    EXPECT_EQ(cache_.get(2), 200);
    EXPECT_EQ(cache_.get(3), 300);
}

TEST_F(LRUCacheTest, DequeOperations) {
    std::vector<int> vec = {5, 7, 3, 4, 9, 1, 2, 6, 8};

    std::sort(vec.begin(), vec.end());

    for (int n : vec) {
        std::printf("%d ", n);
    }
    std::printf("\n");

    std::deque<Person> dq = {
        {"Bucky", 50},
        {"Hercules", 62},
        {"Chief", 56},
    };

    printf("#people: %zu\n", dq.size());
    for (Person p : dq) {
        printf("%s: %d\n", p.name, p.age);
    }

    auto by_age = [](const Person& left, const Person& right) {
        return left.age > right.age;
    };
    std::priority_queue<Person, std::vector<Person>, decltype(by_age)> pq(by_age);
    for (Person p : dq) {
        pq.push(p);
    }
    pq.push({"Biff", 38});

    while (pq.size() > 0) {
        Person top = pq.top();
        printf("top: {%s, %d}\n", top.name, top.age);
        pq.pop();
    }
}

}