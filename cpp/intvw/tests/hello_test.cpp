import hello;

#include <cassert>
#include <iostream>
#include <string>

int main() {
    const std::string result = intvw::hello_world();
    assert(result == "Hello World");
    std::cout << "hello_test passed: \"" << result << "\"\n";
    return 0;
}
