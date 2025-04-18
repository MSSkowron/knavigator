// repeat_task.go
package engine

import (
	"context"
	"fmt"
	"time"

	"gopkg.in/yaml.v3"
	log "k8s.io/klog/v2"

	"github.com/NVIDIA/knavigator/pkg/config"
)

type RepeatTask struct {
	BaseTask
	repeatTaskParams
	engine Engine
}

type repeatTaskParams struct {
	Duration string        `yaml:"duration"`
	Count    int           `yaml:"count"`
	Interval string        `yaml:"interval"`
	Tasks    []config.Task `yaml:"tasks"`

	parsedDuration time.Duration
	parsedInterval time.Duration
}

func newRepeatTask(eng Engine, cfg *config.Task) (*RepeatTask, error) {
	if eng == nil {
		return nil, fmt.Errorf("%s/%s: Engine is not set", cfg.Type, cfg.ID)
	}
	task := &RepeatTask{
		BaseTask: BaseTask{
			taskType: cfg.Type,
			taskID:   cfg.ID,
		},
		engine: eng,
	}
	if err := task.validate(cfg.Params); err != nil {
		return nil, err
	}
	return task, nil
}

func (task *RepeatTask) validate(params map[string]interface{}) error {
	data, err := yaml.Marshal(params)
	if err != nil {
		return fmt.Errorf("%s: failed to marshal parameters: %v", task.ID(), err)
	}
	if err = yaml.Unmarshal(data, &task.repeatTaskParams); err != nil {
		return fmt.Errorf("%s: failed to unmarshal parameters: %v", task.ID(), err)
	}

	if task.Duration == "" && task.Count <= 0 {
		return fmt.Errorf("%s: must specify either 'duration' (e.g., \"10m\") or a positive 'count'", task.ID())
	}
	if task.Duration != "" {
		task.parsedDuration, err = time.ParseDuration(task.Duration)
		if err != nil {
			return fmt.Errorf("%s: failed to parse duration '%s': %v", task.ID(), task.Duration, err)
		}
	} else {
		task.parsedDuration = 0
	}

	if task.Interval != "" {
		task.parsedInterval, err = time.ParseDuration(task.Interval)
		if err != nil {
			return fmt.Errorf("%s: failed to parse interval '%s': %v", task.ID(), task.Interval, err)
		}
	} else {
		task.parsedInterval = 0
	}

	if len(task.Tasks) == 0 {
		return fmt.Errorf("%s: 'tasks' list cannot be empty", task.ID())
	}
	for i, subCfg := range task.Tasks {
		if subCfg.Type == "" {
			return fmt.Errorf("%s: sub-task at index %d is missing 'type'", task.ID(), i)
		}
		if subCfg.ID != "" {
			log.Infof("Task %s: sub-task %s/%s (index %d) has a defined 'id'. This ID will be ignored and dynamically generated within the loop to avoid conflicts.", task.ID(), subCfg.Type, subCfg.ID, i)
		}
	}

	return nil
}

func (task *RepeatTask) Exec(ctx context.Context) error {
	startTime := time.Now()
	iterations := 0

	log.Infof("Task %s starting loop (duration: %s, count: %d, interval: %s)",
		task.ID(), task.Duration, task.Count, task.Interval)

	for {
		durationLimitReached := (task.parsedDuration > 0 && time.Since(startTime) >= task.parsedDuration)
		countLimitReached := (task.Count > 0 && iterations >= task.Count)

		if durationLimitReached || countLimitReached {
			logMsg := fmt.Sprintf("Task %s finished loop. Reason:", task.ID())
			if durationLimitReached {
				logMsg += fmt.Sprintf(" duration limit %s reached (elapsed: %s)", task.parsedDuration, time.Since(startTime).Round(time.Second))
			}
			if countLimitReached {
				if durationLimitReached {
					logMsg += " and"
				}
				logMsg += fmt.Sprintf(" count limit %d reached (iterations: %d)", task.Count, iterations)
			}
			log.Info(logMsg)
			break
		}

		select {
		case <-ctx.Done():
			log.Warningf("Task %s cancelled before iteration %d: %v", task.ID(), iterations+1, ctx.Err())
			return ctx.Err()
		default:
		}

		log.V(1).Infof("Task %s starting iteration %d", task.ID(), iterations+1)

		for i, subCfgTemplate := range task.Tasks {
			subCfg := subCfgTemplate
			originalID := subCfgTemplate.ID
			subCfg.ID = fmt.Sprintf("%s-iter%d-sub%d", task.taskID, iterations, i)
			if originalID != "" {
				log.V(4).Infof("Task %s: generated dynamic ID '%s' for sub-task template (original ID: %s)", task.ID(), subCfg.ID, originalID)
			} else {
				log.V(4).Infof("Task %s: generated dynamic ID '%s' for sub-task template (index %d)", task.ID(), subCfg.ID, i)
			}

			err := task.engine.RunTask(ctx, &subCfg)
			if err != nil {
				log.Errorf("Task %s: dynamically created sub-task %s/%s (index %d, iteration %d) failed: %v", task.ID(), subCfg.Type, subCfg.ID, i, iterations+1, err)
				return fmt.Errorf("sub-task %s/%s failed: %w", subCfg.Type, subCfg.ID, err)
			}

			select {
			case <-ctx.Done():
				log.Warningf("Task %s cancelled after dynamically created sub-task %s/%s: %v", task.ID(), subCfg.Type, subCfg.ID, ctx.Err())
				return ctx.Err()
			default:
			}
		}

		iterations++
		log.V(2).Infof("Task %s completed iteration %d", task.ID(), iterations)

		if task.parsedInterval > 0 {
			log.V(4).Infof("Task %s sleeping for interval %s after iteration %d", task.ID(), task.parsedInterval, iterations)
			select {
			case <-time.After(task.parsedInterval):
			case <-ctx.Done():
				log.Warningf("Task %s cancelled during interval sleep: %v", task.ID(), ctx.Err())
				return ctx.Err()
			}
		}
	}

	return nil
}
