module;

#include <algorithm>
#include <limits>
#include <map>
#include <queue>
#include <string>
#include <vector>

export module hello;

export namespace intvw {

std::string hello_world() {
    return "Hello World";
}

int closestXY2D(std::string input) {

    int lastX = -1, lastY = -1;
    int mindist = std::numeric_limits<int>::max();

    for (size_t i = 0; i < input.size(); ++i) {
        if (input[i] == 'X') {
            if (lastY >= 0) {
                mindist = std::min(mindist, static_cast<int>(i) - lastY);
            }
            lastX = static_cast<int>(i);
        } else if (input[i] == 'Y') {
            if (lastX >= 0) {
                mindist = std::min(mindist, static_cast<int>(i) - lastX);
            }
            lastY = static_cast<int>(i);
        }
    }
    return mindist;
}

struct Point2D {
    int r, c;
    auto operator<=>(const Point2D&) const = default;
};

struct Point2DCost {
    int cost;
    Point2D pt;
};

int demoRobot(std::vector<std::vector<int>> grid) {

    const int N = grid.size();

    const Point2D DIRS[] = {{-1, 0}, {0, 1}, {1, 0}, {0, -1}};

    const Point2D origin = Point2D{0, 0};

    // lowest cost to reach each point
    std::map<Point2D, int> cost = {{origin, 0}};

    // lowest cost path predecessor
    std::map<Point2D, Point2D> prev;

    // queue based on min cost
    std::priority_queue<
        Point2DCost, 
        std::vector<Point2DCost>, 
        decltype([](const Point2DCost& a, const Point2DCost& b) {
            // TODO: use cost map instead and get rid of Point2DCost
            return a.cost > b.cost;
        })
    > pq;

    pq.push(Point2DCost{0, origin});

    while (!pq.empty()) {

        const Point2DCost cur = pq.top();
        pq.pop();

        if (cur.pt.r == N-1 && cur.pt.c == N-1) {
            return cur.cost;
        }

        for (const Point2D dir : DIRS) {
            const Point2D next = {cur.pt.r + dir.r, cur.pt.c + dir.c};
            if (next.r < 0 || next.r >= N || next.c < 0 || next.c >= N) {
                continue;
            }

            int nextCost = cur.cost + grid[next.r][next.c];
            auto existingCost = cost.find(next);
            if (existingCost == cost.end() || nextCost < existingCost->second) {
                cost[next] = nextCost;
                prev[next] = cur.pt;
                pq.push({nextCost, next});
            }
        }
    }

    return std::numeric_limits<int>::max();
}

}
