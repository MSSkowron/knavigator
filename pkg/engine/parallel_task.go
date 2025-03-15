// parallel_task.go
package engine

import (
	"context"
	"fmt"
	"sync"

	"go.uber.org/multierr"
	"gopkg.in/yaml.v3"
	log "k8s.io/klog/v2"

	"github.com/NVIDIA/knavigator/pkg/config"
)

type ParallelTask struct {
	BaseTask
	parallelTaskParams
	engine Engine
}

type parallelTaskParams struct {
	Tasks []config.Task `yaml:"tasks"`
}

func newParallelTask(eng Engine, cfg *config.Task) (*ParallelTask, error) {
	if eng == nil {
		return nil, fmt.Errorf("%s/%s: Engine is not set", cfg.Type, cfg.ID)
	}
	task := &ParallelTask{
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

func (task *ParallelTask) validate(params map[string]interface{}) error {
	data, err := yaml.Marshal(params)
	if err != nil {
		return fmt.Errorf("%s: failed to marshal parameters: %v", task.ID(), err)
	}
	if err = yaml.Unmarshal(data, &task.parallelTaskParams); err != nil {
		return fmt.Errorf("%s: failed to unmarshal parameters: %v", task.ID(), err)
	}

	if len(task.Tasks) == 0 {
		return fmt.Errorf("%s: 'tasks' list cannot be empty for Parallel task", task.ID())
	}
	for i, subCfg := range task.Tasks {
		if subCfg.Type == "" {
			return fmt.Errorf("%s: sub-task at index %d is missing 'type'", task.ID(), i)
		}
		if subCfg.ID != "" {
			log.Infof("Task %s: sub-task %s/%s (index %d) has a defined 'id'. This ID will be ignored and dynamically generated during parallel execution to avoid conflicts.", task.ID(), subCfg.Type, subCfg.ID, i)
		}
	}
	return nil
}

func (task *ParallelTask) Exec(ctx context.Context) error {
	var wg sync.WaitGroup
	var allErrors error
	var errMutex sync.Mutex

	log.Infof("Task %s launching %d sub-tasks in parallel", task.ID(), len(task.Tasks))

	runnables := make([]Runnable, 0, len(task.Tasks))
	dynamicSubTaskIDs := make([]string, len(task.Tasks))

	for i, subCfgTemplate := range task.Tasks {
		subCfg := subCfgTemplate
		originalID := subCfgTemplate.ID
		dynamicID := fmt.Sprintf("%s-parallel-sub%d", task.taskID, i)
		subCfg.ID = dynamicID
		dynamicSubTaskIDs[i] = dynamicID

		if originalID != "" {
			log.V(4).Infof("Task %s: generated dynamic ID '%s' for parallel sub-task template (original ID: %s)", task.ID(), subCfg.ID, originalID)
		} else {
			log.V(4).Infof("Task %s: generated dynamic ID '%s' for parallel sub-task template (index %d)", task.ID(), subCfg.ID, i)
		}

		runnable, err := task.engine.GetTask(&subCfg)
		if err != nil {
			log.Errorf("Task %s: failed to prepare sub-task %s/%s (index %d): %v. Aborting parallel execution.", task.ID(), subCfg.Type, subCfg.ID, i, err)
			return fmt.Errorf("failed to prepare sub-task %s/%s: %w", subCfg.Type, subCfg.ID, err)
		}
		runnables = append(runnables, runnable)
	}

	for idx, runnable := range runnables {
		wg.Add(1)
		go func(r Runnable, subTaskDynamicID string) {
			defer wg.Done()
			err := execRunnable(ctx, r)
			if err != nil {
				errMutex.Lock()

				allErrors = multierr.Append(allErrors, fmt.Errorf("sub-task %s failed: %w", subTaskDynamicID, err))
				errMutex.Unlock()
			} else {
				log.V(1).Infof("Task %s: parallel sub-task %s completed successfully", task.ID(), subTaskDynamicID)
			}
		}(runnable, dynamicSubTaskIDs[idx])
	}

	wg.Wait()

	if allErrors != nil {
		log.Errorf("Task %s finished with errors from parallel sub-tasks", task.ID())
		return allErrors
	}

	log.Infof("Task %s successfully completed all parallel sub-tasks", task.ID())
	return nil
}
