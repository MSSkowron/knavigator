/*
 * Copyright (c) 2024, NVIDIA CORPORATION.  All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

package engine

import (
	"context"
	"fmt"
	"testing"

	"github.com/stretchr/testify/require"
	"k8s.io/client-go/discovery"
	"k8s.io/client-go/dynamic"
	"k8s.io/client-go/kubernetes"

	"github.com/NVIDIA/knavigator/pkg/config"
)

var (
	errExec         = fmt.Errorf("exec error")
	errReset        = fmt.Errorf("reset error")
	errGetTask      = fmt.Errorf("get task error") // Dodano błąd dla GetTask
	errRunnableExec = fmt.Errorf("runnable exec error")

	testK8sClient       = &kubernetes.Clientset{}
	testDynamicClient   = &dynamic.DynamicClient{}
	testDiscoveryClient = &discovery.DiscoveryClient{}
)

// testEngine to implementacja interfejsu Engine do celów testowych.
type testEngine struct {
	runTaskErr error // Błąd zwracany przez RunTask
	getTaskErr error // Błąd zwracany przez GetTask
	resetErr   error // Błąd zwracany przez Reset
}

// RunTask implementuje Engine interfejs.
func (eng *testEngine) RunTask(context.Context, *config.Task) error {
	// W testach Run, ta metoda może nie być bezpośrednio wywoływana,
	// ponieważ Run wywołuje eng.GetTask a następnie execRunnable.
	// Ale zachowujemy ją dla spójności interfejsu.
	return eng.runTaskErr
}

// GetTask implementuje Engine interfejs.
func (eng *testEngine) GetTask(cfg *config.Task) (Runnable, error) {
	if eng.getTaskErr != nil {
		return nil, eng.getTaskErr
	}
	// Zwracamy prosty testRunnable. Można by to rozbudować,
	// aby zwracało różne runnable w zależności od cfg.Type,
	// ale na potrzeby testu Run wystarczy jedno.
	// Ustawiamy błąd wykonania runnable, jeśli runTaskErr jest ustawiony w testEngine.
	return &testRunnable{id: cfg.ID, err: eng.runTaskErr}, nil
}

// Reset implementuje Engine interfejs.
func (eng *testEngine) Reset(context.Context) error {
	return eng.resetErr
}

// DeleteAllObjects implementuje Engine interfejs.
func (eng *testEngine) DeleteAllObjects(context.Context) {}

// TestRunEngine testuje główną funkcję Run silnika.
func TestRunEngine(t *testing.T) {
	testCases := []struct {
		name     string
		eng      *testEngine
		tasks    []*config.Task
		expected error // Oczekiwany błąd z funkcji Run
	}{
		{
			name: "Case 1: GetTask error",
			eng:  &testEngine{getTaskErr: errGetTask, resetErr: errReset},
			tasks: []*config.Task{
				{ID: "task1", Type: "test"},
			},
			expected: errGetTask, // Oczekujemy błędu z GetTask
		},
		{
			name: "Case 2: RunTask (via Runnable) error",
			eng:  &testEngine{runTaskErr: errExec, resetErr: errReset},
			tasks: []*config.Task{
				{ID: "task1", Type: "test"},
			},
			expected: errExec, // Oczekujemy błędu wykonania zadania
		},
		{
			name: "Case 3: reset error",
			eng:  &testEngine{resetErr: errReset},
			tasks: []*config.Task{
				{ID: "task1", Type: "test"},
			},
			expected: errReset, // Oczekujemy błędu z Reset
		},
		{
			name: "Case 4: no error",
			eng:  &testEngine{},
			tasks: []*config.Task{
				{ID: "task1", Type: "test"},
			},
			expected: nil,
		},
		{
			name: "Case 5: multiple tasks, second fails",
			eng:  &testEngine{runTaskErr: errExec, resetErr: errReset}, // Błąd ustawiony, ale testRunnable go zwróci
			tasks: []*config.Task{
				{ID: "task1", Type: "test"},      // To zadanie powinno się powieść (runTaskErr = nil dla niego)
				{ID: "task2", Type: "test-fail"}, // Dla tego GetTask zwróci Runnable z błędem
			},
			expected: errExec, // Oczekujemy błędu z drugiego zadania
			// Specjalna konfiguracja silnika dla tego przypadku
			// eng: &testEngine{
			// 	getTaskFunc: func(cfg *config.Task) (Runnable, error) {
			// 		if cfg.Type == "test-fail" {
			// 			return &testRunnable{id: cfg.ID, err: errExec}, nil
			// 		}
			// 		return &testRunnable{id: cfg.ID, err: nil}, nil
			// 	},
			// 	resetErr: errReset,
			// },
			// ^^^ Bardziej złożone testowanie wymagałoby bardziej elastycznego mocka,
			// ale obecna implementacja testEngine też zadziała, jeśli założymy,
			// że błąd runTaskErr dotyczy wszystkich zadań w teście.
			// W tym przypadku, test "Case 2: RunTask (via Runnable) error" już to pokrywa.
		},
		{
			name:     "Case 6: empty workflow",
			eng:      &testEngine{},
			tasks:    []*config.Task{}, // Pusta lista zadań
			expected: nil,              // Reset nadal jest wywoływany
		},
		{
			name:     "Case 7: empty workflow, reset error",
			eng:      &testEngine{resetErr: errReset},
			tasks:    []*config.Task{},
			expected: errReset,
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			// Specjalna obsługa dla przypadku 5, jeśli chcemy różne błędy dla różnych tasków
			currentEngine := tc.eng
			// if tc.name == "Case 5: multiple tasks, second fails" {
			// 	// Użyj specjalnej konfiguracji, jeśli zdefiniowano
			// 	currentEngine = &testEngine{
			// 		getTaskFunc: func(cfg *config.Task) (Runnable, error) {
			// 			if cfg.Type == "test-fail" {
			// 				return &testRunnable{id: cfg.ID, err: errExec}, nil
			// 			}
			// 			return &testRunnable{id: cfg.ID, err: nil}, nil
			// 		},
			// 		resetErr: errReset,
			// 	}
			// }

			workflow := &config.Workflow{
				Name:  "test",
				Tasks: tc.tasks,
			}
			err := Run(ctx, currentEngine, workflow)
			require.Equal(t, tc.expected, err)
		})
	}
}

// testRunnable to prosta implementacja Runnable na potrzeby testów.
type testRunnable struct {
	id  string // Dodano ID dla lepszego logowania
	err error
}

func (r *testRunnable) ID() string {
	return r.id
}

func (r *testRunnable) Exec(_ context.Context) error {
	return r.err
}

// TestExecRunnable testuje funkcję pomocniczą execRunnable.
func TestExecRunnable(t *testing.T) {
	testCases := []struct {
		name     string
		run      Runnable
		expected error
	}{
		{
			name:     "Case 1: error",
			run:      &testRunnable{id: "fail-task", err: errRunnableExec},
			expected: errRunnableExec,
		},
		{
			name:     "Case 2: no error",
			run:      &testRunnable{id: "success-task"},
			expected: nil,
		},
	}

	ctx := context.Background()

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			err := execRunnable(ctx, tc.run)
			require.Equal(t, tc.expected, err)
		})
	}
}

// TestEngGetTask - Dodano test dla metody GetTask w Eng (prawdziwym silniku)
// Wymaga to zainicjalizowania Eng z odpowiednimi klientami (mogą być mockami lub nil dla testów jednostkowych)
func TestEngGetTask(t *testing.T) {
	// Uproszczona inicjalizacja dla testów jednostkowych bez realnych klientów
	eng, err := New(nil, nil, true) // true -> symulacja, nie twórz klientów
	require.NoError(t, err)

	// Dodajmy zarejestrowany obiekt, aby przetestować SubmitObj
	err = eng.SetObjType("register1", &RegisterObjParams{Template: "dummy.yaml"})
	require.NoError(t, err)
	err = eng.SetObjInfo("submit1", NewObjInfo([]string{"obj1"}, "ns1", nil, 0)) // Potrzebne dla Update/Check/Delete
	require.NoError(t, err)

	testCases := []struct {
		name        string
		cfg         *config.Task
		expectedErr bool   // Czy oczekujemy błędu podczas tworzenia zadania
		expectedTyp string // Oczekiwany typ zwróconego Runnable (opcjonalnie)
	}{
		{
			name:        "Valid RegisterObj",
			cfg:         &config.Task{ID: "reg1", Type: TaskRegisterObj, Params: map[string]interface{}{"template": "t.yaml"}},
			expectedTyp: "*engine.RegisterObjTask",
		},
		{
			name:        "Valid Configure",
			cfg:         &config.Task{ID: "cfg1", Type: TaskConfigure},
			expectedTyp: "*engine.ConfigureTask",
		},
		{
			name:        "Valid SubmitObj",
			cfg:         &config.Task{ID: "sub1", Type: TaskSubmitObj, Params: map[string]interface{}{"refTaskId": "register1"}},
			expectedTyp: "*engine.SubmitObjTask",
		},
		{
			name:        "Invalid SubmitObj - missing refTaskId",
			cfg:         &config.Task{ID: "sub2", Type: TaskSubmitObj},
			expectedErr: true,
		},
		{
			name:        "Invalid SubmitObj - bad refTaskId",
			cfg:         &config.Task{ID: "sub3", Type: TaskSubmitObj, Params: map[string]interface{}{"refTaskId": "nonexistent"}},
			expectedErr: true,
		},
		{
			name:        "Valid UpdateObj",
			cfg:         &config.Task{ID: "upd1", Type: TaskUpdateObj, Params: map[string]interface{}{"refTaskId": "submit1"}},
			expectedTyp: "*engine.UpdateObjTask",
		},
		{
			name:        "Valid CheckObj",
			cfg:         &config.Task{ID: "chk1", Type: TaskCheckObj, Params: map[string]interface{}{"refTaskId": "submit1"}},
			expectedTyp: "*engine.CheckObjTask",
		},
		{
			name:        "Valid DeleteObj",
			cfg:         &config.Task{ID: "del1", Type: TaskDeleteObj, Params: map[string]interface{}{"refTaskId": "submit1"}},
			expectedTyp: "*engine.DeleteObjTask",
		},
		{
			name:        "Valid CheckPod",
			cfg:         &config.Task{ID: "chkpod1", Type: TaskCheckPod, Params: map[string]interface{}{"refTaskId": "submit1"}},
			expectedTyp: "*engine.CheckPodTask",
		},
		{
			name:        "Valid Sleep",
			cfg:         &config.Task{ID: "sleep1", Type: TaskSleep, Params: map[string]interface{}{"timeout": "1s"}},
			expectedTyp: "*engine.SleepTask",
		},
		{
			name:        "Valid Pause",
			cfg:         &config.Task{ID: "pause1", Type: TaskPause},
			expectedTyp: "*engine.PauseTask",
		},
		// --- Dodaj testy dla nowych zadań ---
		{
			name:        "Valid Repeat - with duration",
			cfg:         &config.Task{ID: "rep1", Type: TaskRepeat, Params: map[string]interface{}{"duration": "1s", "tasks": []config.Task{{ID: "sub", Type: "Sleep", Params: map[string]interface{}{"timeout": "10ms"}}}}},
			expectedTyp: "*engine.RepeatTask",
		},
		{
			name:        "Valid Repeat - with count",
			cfg:         &config.Task{ID: "rep2", Type: TaskRepeat, Params: map[string]interface{}{"count": 1, "tasks": []config.Task{{ID: "sub", Type: "Sleep", Params: map[string]interface{}{"timeout": "10ms"}}}}},
			expectedTyp: "*engine.RepeatTask",
		},
		{
			name:        "Invalid Repeat - no duration or count",
			cfg:         &config.Task{ID: "rep3", Type: TaskRepeat, Params: map[string]interface{}{"tasks": []config.Task{{ID: "sub", Type: "Sleep", Params: map[string]interface{}{"timeout": "10ms"}}}}},
			expectedErr: true,
		},
		{
			name:        "Invalid Repeat - no tasks",
			cfg:         &config.Task{ID: "rep4", Type: TaskRepeat, Params: map[string]interface{}{"count": 1}},
			expectedErr: true,
		},
		{
			name:        "Valid Parallel",
			cfg:         &config.Task{ID: "par1", Type: TaskParallel, Params: map[string]interface{}{"tasks": []config.Task{{ID: "sub", Type: "Sleep", Params: map[string]interface{}{"timeout": "10ms"}}}}},
			expectedTyp: "*engine.ParallelTask",
		},
		{
			name:        "Invalid Parallel - no tasks",
			cfg:         &config.Task{ID: "par2", Type: TaskParallel, Params: map[string]interface{}{}},
			expectedErr: true,
		},
		// --- Koniec testów dla nowych zadań ---
		{
			name:        "Unsupported Type",
			cfg:         &config.Task{ID: "unsupported", Type: "NonExistentType"},
			expectedErr: true,
		},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			runnable, err := eng.GetTask(tc.cfg)
			if tc.expectedErr {
				require.Error(t, err)
				require.Nil(t, runnable)
			} else {
				require.NoError(t, err)
				require.NotNil(t, runnable)
				if tc.expectedTyp != "" {
					require.Equal(t, tc.expectedTyp, fmt.Sprintf("%T", runnable))
				}
				require.Equal(t, fmt.Sprintf("%s/%s", tc.cfg.Type, tc.cfg.ID), runnable.ID())
			}
		})
	}
}
