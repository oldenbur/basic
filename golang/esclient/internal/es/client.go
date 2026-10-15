// Package es provides shared construction of Elasticsearch clients for the sandbox commands.
package es

import (
	"fmt"

	"github.com/elastic/go-elasticsearch/v9"
)

// New returns a typed Elasticsearch client for the server at url.
func New(url string) (*elasticsearch.TypedClient, error) {
	client, err := elasticsearch.NewTypedClient(elasticsearch.Config{
		Addresses: []string{url},
	})
	if err != nil {
		return nil, fmt.Errorf("create elasticsearch client: %w", err)
	}
	return client, nil
}
