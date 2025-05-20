package engine

import (
	"context"
	"errors"
	"fmt"
	"time"

	apierrors "k8s.io/apimachinery/pkg/api/errors"
	metav1 "k8s.io/apimachinery/pkg/apis/meta/v1"
	"k8s.io/apimachinery/pkg/runtime/schema"
	"k8s.io/apimachinery/pkg/util/wait"
	"k8s.io/client-go/dynamic"
	log "k8s.io/klog/v2"

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

// Exec usuwa wszystkie Joby (batch/v1) i VolcanoJoby (batch.volcano.sh/v1alpha1),
// a następnie czeka, aż w klastrze nie zostanie żaden z tych zasobów.
func (t *DeleteAllJobsTask) Exec(ctx context.Context) error {
	deletePolicy := metav1.DeletePropagationBackground
	delOpts := metav1.DeleteOptions{PropagationPolicy: &deletePolicy}

	gvrs := []schema.GroupVersionResource{
		{Group: "batch", Version: "v1", Resource: "jobs"},
		{Group: "batch.volcano.sh", Version: "v1alpha1", Resource: "jobs"},
	}

	log.Infof("Task %s: starting deletion of all jobs", t.ID())
	for _, gvr := range gvrs {
		log.Infof("Task %s: processing resource %s", t.ID(), gvr.String())

		// 1) Pobierz listę
		list, err := t.dynamicClient.
			Resource(gvr).
			Namespace(metav1.NamespaceAll).
			List(ctx, metav1.ListOptions{})
		if err != nil {
			if apierrors.IsNotFound(err) {
				log.Infof("Task %s: resource %s not found, skipping", t.ID(), gvr.String())
				continue
			}
			log.Errorf("Task %s: error listing %s: %v", t.ID(), gvr.String(), err)
			return fmt.Errorf("%s: błąd listowania %s: %w", t.ID(), gvr.String(), err)
		}
		log.Infof("Task %s: found %d items for %s", t.ID(), len(list.Items), gvr.String())

		// 2) Usuń każdy
		for _, obj := range list.Items {
			ns, name := obj.GetNamespace(), obj.GetName()
			log.Infof("Task %s: deleting %s %s/%s", t.ID(), gvr.String(), ns, name)
			if err := t.dynamicClient.
				Resource(gvr).
				Namespace(ns).
				Delete(ctx, name, delOpts); err != nil {
				if apierrors.IsNotFound(err) {
					log.Infof("Task %s: %s %s/%s already deleted, skipping", t.ID(), gvr.String(), ns, name)
					continue
				}
				log.Errorf("Task %s: error deleting %s %s/%s: %v", t.ID(), gvr.String(), ns, name, err)
				return fmt.Errorf("%s: błąd usuwania %s %s/%s: %w", t.ID(), gvr.String(), ns, name, err)
			}
		}

		// 3) Polling na brak pozostałości
		log.Infof("Task %s: waiting up to 2m for deletion of %s", t.ID(), gvr.String())
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
					if apierrors.IsNotFound(err) {
						return true, nil
					}
					return false, err
				}
				return len(l.Items) == 0, nil
			},
		)
		if err != nil {
			if errors.Is(err, context.DeadlineExceeded) {
				log.Errorf("Task %s: timeout waiting for deletion of %s", t.ID(), gvr.String())
				return fmt.Errorf("%s: timeout oczekiwania na usunięcie wszystkich %s", t.ID(), gvr.String())
			}
			log.Errorf("Task %s: error while waiting for deletion of %s: %v", t.ID(), gvr.String(), err)
			return fmt.Errorf("%s: błąd podczas oczekiwania na czyszczenie %s: %w", t.ID(), gvr.String(), err)
		}
		log.Infof("Task %s: confirmed deletion of all %s", t.ID(), gvr.String())
	}

	log.Infof("Task %s: successfully deleted all jobs", t.ID())
	return nil
}
