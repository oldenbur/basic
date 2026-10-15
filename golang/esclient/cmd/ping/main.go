// Command ping checks connectivity to the Elasticsearch sandbox and prints basic cluster info.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"time"

	"esclient/internal/es"
)

func main() {
	defaultURL := os.Getenv("ES_URL")
	if defaultURL == "" {
		defaultURL = "http://localhost:9200"
	}
	url := flag.String("url", defaultURL, "Elasticsearch URL (env ES_URL)")
	timeout := flag.Duration("timeout", 5*time.Second, "request timeout")
	flag.Parse()

	if err := run(*url, *timeout); err != nil {
		fmt.Fprintf(os.Stderr, "ping failed: %v\n", err)
		os.Exit(1)
	}
}

func run(url string, timeout time.Duration) error {
	client, err := es.New(url)
	if err != nil {
		return err
	}

	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	ok, err := client.Ping().IsSuccess(ctx)
	if err != nil {
		return fmt.Errorf("ping %s: %w", url, err)
	}
	if !ok {
		return fmt.Errorf("ping %s: unexpected response", url)
	}

	info, err := client.Info().Do(ctx)
	if err != nil {
		return fmt.Errorf("info %s: %w", url, err)
	}

	fmt.Printf("connected to %s\n", url)
	fmt.Printf("  cluster: %s\n", info.ClusterName)
	fmt.Printf("  node:    %s\n", info.Name)
	fmt.Printf("  version: %s\n", info.Version.Int)
	fmt.Printf("  tagline: %s\n", info.Tagline)
	return nil
}
