package main

import (
	"fmt"
	"github.com/cihub/seelog"
	"github.com/stretchr/testify/assert"
	"testing"
	"time"
)

func init() { setupLogging() }

func TestConfigString(t *testing.T) {
	defer seelog.Flush()

	json := NewConfigBuilder().Build().MarshalJSON()
	assert.Equal(t, string(json),
		fmt.Sprintf(
			configJSONTemplate,
			time.Local,
			scheduleAheadDurationDefault,
			registerRetryWaitDefault,
			registerRetryMaxDefault,
			registerRetryLogIntvlDefault,
		),
	)
}
