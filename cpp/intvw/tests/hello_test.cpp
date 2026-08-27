import hello;

#include <gtest/gtest.h>

TEST(HelloTest, ReturnsHelloWorld) {
    EXPECT_EQ(intvw::hello_world(), "Hello World");
}

TEST(ClosestXY2DTest, MultipleXsYs) {
    EXPECT_EQ(intvw::closestXY2D("OXOOYOXOOY"), 2);
    EXPECT_EQ(intvw::closestXY2D("OXOOYOXXOY"), 2);
    EXPECT_EQ(intvw::closestXY2D("OXOOYYOXXOOY"), 2);
}

TEST(DemoRobotTest, StandardMaze) {
    std::vector<std::vector<int>> maze0 = {
        {0, 1, 0, 0},
        {0, 1, 1, 1},
        {0, 0, 0, 0},
        {0, 1, 1, 0},
    };
    EXPECT_EQ(intvw::demoRobot(maze0), 0);
    std::vector<std::vector<int>> maze1 = {
        {0, 1, 0, 0},
        {0, 1, 1, 1},
        {0, 0, 1, 0},
        {0, 1, 1, 0},
    };
    EXPECT_EQ(intvw::demoRobot(maze1), 1);
    std::vector<std::vector<int>> maze2 = {
        {0, 1, 0, 0},
        {0, 1, 1, 1},
        {0, 1, 1, 0},
        {0, 1, 1, 0},
    };
    EXPECT_EQ(intvw::demoRobot(maze2), 2);
}
