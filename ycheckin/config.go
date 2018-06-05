package main

import (
	"fmt"
	"time"
)

const (
	httpAddrDefault              = "0.0.0.0:8989"
	scheduleAheadDurationDefault = 48 * time.Hour
	registerRetryWaitDefault     = time.Second
	registerRetryMaxDefault      = 3600
	registerRetryLogIntvlDefault = 100

	configJSONTemplate = `{
  "location": "%v",
  "schedAheadDur": "%v",
  "regRetryWait": "%v",
  "regRetryMax": %d,
  "regRetryLogIntvl": %d
}`
)

func NewConfigBuilder() *configBuilder {
	return &configBuilder{&ycheckinConfig{
		time.Local,
		httpAddrDefault,
		scheduleAheadDurationDefault,
		registerRetryWaitDefault,
		registerRetryMaxDefault,
		registerRetryLogIntvlDefault,
	}}
}

type configBuilder struct {
	config *ycheckinConfig
}

func (c *configBuilder) WithLocation(loc *time.Location) *configBuilder {
	c.config.loc = loc
	return c
}

func (c *configBuilder) WithHttpAddr(httpAddr string) *configBuilder {
	c.config.httpAddr = httpAddr
	return c
}

func (c *configBuilder) WithScheduleAheadDuration(d time.Duration) *configBuilder {
	c.config.schedAheadDur = d
	return c
}

func (c *configBuilder) WithRegisterRetryWait(d time.Duration) *configBuilder {
	c.config.registerRetryWait = d
	return c
}

func (c *configBuilder) WithRegisterRetryMax(i int) *configBuilder {
	c.config.registerRetryMax = i
	return c
}

func (c *configBuilder) WithRegisterRetryLogIntvl(i int) *configBuilder {
	c.config.registerRetryLogIntvl = i
	return c
}

func (c *configBuilder) Build() *ycheckinConfig {
	return c.config
}

type ycheckinConfig struct {
	loc                   *time.Location
	httpAddr              string
	schedAheadDur         time.Duration
	registerRetryWait     time.Duration
	registerRetryMax      int
	registerRetryLogIntvl int
}

func (c *ycheckinConfig) RegisterLocation() *time.Location     { return c.loc }
func (c *ycheckinConfig) ScheduleAheadDuration() time.Duration { return c.schedAheadDur }
func (c *ycheckinConfig) RegisterRetryWait() time.Duration     { return c.registerRetryWait }
func (c *ycheckinConfig) RegisterRetryMax() int                { return c.registerRetryMax }
func (c *ycheckinConfig) RegisterRetryLogIntvl() int           { return c.registerRetryLogIntvl }
func (c *ycheckinConfig) HttpAddr() string                     { return c.httpAddr }
func (c *ycheckinConfig) MarshalJSON() string {
	return fmt.Sprintf(configJSONTemplate, c.loc, c.schedAheadDur, c.registerRetryWait, c.registerRetryMax, c.registerRetryLogIntvl)
}
