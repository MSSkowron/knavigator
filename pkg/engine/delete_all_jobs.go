package engine

import (
	"context"
	"errors"
	"fmt"
	"time"

	k8serrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/client-go/dynamic"

	"github.com/NVIDIA/knavigator/pkg/config"
)

// DeleteAllJobsTask usuwa wszystkie Joby K8s i VolcanoJoby we wszystkich namespace'ach.
type DeleteAllJobsTask struct {
	BaseTask
	dynamicClient dynamic.Interface
}

func newDeleteAllJobsTask(dynamicClient dynamic.Interface, cfg *config.Task) (*DeleteAllJobsTask, error) {
	if len(cfg.Params) != 0 {
		return nil, fmt.Errorf("%s: DeleteAllJobs nie przyjmuje parametrów", cfg.ID)
	}
	return &DeleteAllJobsTask{
		BaseTask: BaseTask{
			taskType: cfg.Type,
			taskID:   cfg.ID,
		},
		dynamicClient: dynamicClient,
	}, nil
}

func (t *DeleteAllJobsTask) Exec(ctx context.Context) error {
	// Propagacja usuwania w tle (cascade deletion)
	deletePolicy := metav1.DeletePropagationBackground
	delOpts := metav1.DeleteOptions{PropagationPolicy: &deletePolicy}

	// ResourceGVR dla standardowych Jobów i dla VolcanoJobów
	gvrs := []schema.GroupVersionResource{
		{Group: "batch", Version: "v1", Resource: "jobs"},
		{Group: "batch.volcano.sh", Version: "v1", Resource: "jobs"},
	}

	for _, gvr := range gvrs {
		// 1) Lista wszystkich obiektów danego typu
		list, err := t.dynamicClient.
			Resource(gvr).
			Namespace(metav1.NamespaceAll).
			List(ctx, metav1.ListOptions{})
		if err != nil {
			// jeśli API nie zna w ogóle tego GVR → pomiń, bez błędu
			if k8serrors.IsNotFound(err) {
				continue
			}
			return fmt.Errorf("%s: błąd listowania %s: %w", t.ID(), gvr.String(), err)
		}

		// 2) Usuń każdy obiekt z listy
		for _, obj := range list.Items {
			ns := obj.GetNamespace()
			name := obj.GetName()
			if err := t.dynamicClient.
				Resource(gvr).
				Namespace(ns).
				Delete(ctx, name, delOpts); err != nil {
				// jeśli zasób już zniknął przed Delete() → pomiń
				if k8serrors.IsNotFound(err) {
					continue
				}
				return fmt.Errorf("%s: błąd usuwania %s %s/%s: %w",
					t.ID(), gvr.String(), ns, name, err)
			}
		}

		// 3) Polling: czekaj do 2 minut, sprawdzając co 2s, aż żadne nie zostaną
		err = wait.PollUntilContextTimeout(
			ctx,
			2*time.Second,
			2*time.Minute,
			true,
			func(ctx context.Context) (bool, error) {
				l, err := t.dynamicClient.
					Resource(gvr).
					Namespace(metav1.NamespaceAll).
					List(ctx, metav1.ListOptions{})
				if err != nil {
					// jeśli API przestało znać GVR w czasie oczekiwania → uznaj za pustą
					if k8serrors.IsNotFound(err) {
						return true, nil
					}
					return false, err
				}
				return len(l.Items) == 0, nil
			},
		)
		if err != nil {
			if errors.Is(err, context.DeadlineExceeded) {
				return fmt.Errorf("%s: timeout oczekiwania na usunięcie wszystkich %s",
					t.ID(), gvr.String())
			}
			return fmt.Errorf("%s: błąd podczas oczekiwania na czyszczenie %s: %w",
				t.ID(), gvr.String(), err)
		}
	}

	return nil
}
