#pragma once

#include <unordered_map>

namespace intvw {

int practice_value();

class LRUCache {
private:
    struct Node {
        int key;
        int value;
        Node* prev;
        Node* next;
        Node(int k, int v): key(k), value(v), prev(nullptr), next(nullptr) {}
    };

    int capacity_;
    Node* head_ = nullptr;
    Node* tail_ = nullptr;
    std::unordered_map<int, Node*> cache_;

public:
    LRUCache(int capacity);
    ~LRUCache();
    int get(int key);
    void put(int key, int value);
};

}
