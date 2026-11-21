//go:build windows

package main

import (
	"archive/zip"
	"bytes"
	_ "embed"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"syscall"
	"unsafe"
)

//go:embed payload.zip
var payload []byte

func unpack(directory string) error {
	archive, err := zip.NewReader(bytes.NewReader(payload), int64(len(payload)))
	if err != nil {
		return err
	}
	for _, entry := range archive.File {
		relative := filepath.FromSlash(entry.Name)
		if !filepath.IsLocal(relative) || filepath.Clean(relative) != relative {
			return fmt.Errorf("invalid runtime path: %s", entry.Name)
		}
		path := filepath.Join(directory, relative)
		if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			return err
		}
		source, err := entry.Open()
		if err != nil {
			return err
		}
		file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if err != nil {
			source.Close()
			return err
		}
		_, copyErr := io.Copy(file, source)
		closeErr := file.Close()
		source.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
	}
	return nil
}

func launch() error {
	directory, err := os.MkdirTemp("", "z-download-manager-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(directory)
	if err := unpack(directory); err != nil {
		return err
	}
	args := []string{"-E", "-s", "-B", filepath.Join(directory, "app.py")}
	args = append(args, os.Args[1:]...)
	command := exec.Command(filepath.Join(directory, "pythonw.exe"), args...)
	command.Dir = directory
	output, err := command.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%w\n%s", err, strings.TrimSpace(string(output)))
	}
	return nil
}

func main() {
	if err := launch(); err != nil {
		if len(os.Args) == 1 {
			title, _ := syscall.UTF16PtrFromString("Z’s Download Manager")
			message, _ := syscall.UTF16PtrFromString("The app could not start.\n\n" + err.Error())
			messageBox := syscall.NewLazyDLL("user32.dll").NewProc("MessageBoxW")
			messageBox.Call(0, uintptr(unsafe.Pointer(message)), uintptr(unsafe.Pointer(title)), 0x10)
		}
		os.Exit(1)
	}
}
