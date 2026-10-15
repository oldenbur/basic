#include "practice.h"

namespace intvw {

int practice_value() {
    return 42;
}

LRUCache::LRUCache(int capacity): capacity_(capacity) {}

LRUCache::~LRUCache() {
    Node* cur = head_;
    while (cur) {
        Node* next = cur->next;
        delete cur;
        cur = next;
    }
}

int LRUCache::get(int key) {
    if (!cache_.contains(key)) {
        return -1;
    }

    Node* valNode = cache_[key];
    if (head_ == valNode) {
        return valNode->value;
    }

    valNode->prev->next = valNode->next;
    if (valNode->next == nullptr) {
        tail_ = valNode->prev;
    } else {
        valNode->next->prev = valNode->prev;
    }
    valNode->next = head_;
    valNode->prev = nullptr;
    head_->prev = valNode;
    head_ = valNode;
    return valNode->value;
}

void LRUCache::put(int key, int value) {
    Node* newNode = new Node(key, value);
    cache_[key] = newNode;

    if (tail_ == nullptr) {
        head_ = newNode;
        tail_ = newNode;
        return;
    }

    tail_->next = newNode;
    newNode->prev = tail_;
    tail_ = newNode;
}

}
