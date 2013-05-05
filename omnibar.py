"""
Copyright (c) 2012 Brett Dixon

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the 
Software, and to permit persons to whom the Software is furnished to do so, 
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all 
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS 
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR 
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER 
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION 
WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

"""File lookup tool"""

import os
import sys
import fnmatch

import sip
sip.setapi('QString', 2)
sip.setapi('QVariant', 2)
from PyQt4 import QtGui, QtCore
import path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


STYLE = """
body { font-family: Verdana; }
body:hover { background: #333; }
h3 { font-size: 14px; margin: 0; padding: 0; }
span { font-weight: bold; color: #2b97ed }
"""
MAIN_STYLE = """
QLineEdit { background: #313437; color: #d2d2d2; border: none; font-family: Verdana; font-size: 16px; padding: 4px; }
"""


class FindItDelegate(QtGui.QStyledItemDelegate):
    """QItemDelegate to display items in the listview"""
    def __init__(self, editor, root, parent=None):
        super(FindItDelegate, self).__init__(parent)
        
        self._editor = editor
        self._root = root + 1
    
    def paint(self, painter, option, index):
        """Override of paaint.  Draws the matched filename and the full path underneath"""
        self.initStyleOption(option, index)
        
        painter.save()
        
        doc = QtGui.QTextDocument()
        doc.setDefaultStyleSheet(STYLE)
        editortext = self._editor.text()
        
        text = '<span>%s</span>%s' % (option.text[:len(editortext)], option.text[len(editortext):])
        filepath = path.path(index.data(FindIt.FILE_ROLE))
        filename = '<span>%s</span>%s' % (filepath.name[:len(editortext)], filepath.name[len(editortext):])
        filepath = filepath.parent / filename
        html = '<body><h3>%s</h3>%s</body>' % (text, filepath[self._root:])
        doc.setHtml(html)
        
        option.text = ''
        QtGui.QApplication.style().drawControl(QtGui.QStyle.CE_ItemViewItem, option, painter)
        
        painter.translate(option.rect.left(), option.rect.top())
        clip = QtCore.QRectF(0, 0, option.rect.width(), option.rect.height())
        doc.drawContents(painter, clip)
        
        painter.restore()
    
    def sizeHint(self, option, index):
        """Returns a QSize to get an appropraite height"""
        return QtCore.QSize(20, 40)


class FindItEvent(FileSystemEventHandler):
    """Event Handler for the watchdog loop"""
    def __init__(self, model, command, mask=None):
        self._model = model
        self._command = command
        self._mask = mask
    
    def addRow(self, file_):
        """Adds a row to the model"""
        item = QtGui.QStandardItem(file_.name)
        item.setData(str(file_), FindIt.FILE_ROLE)
        item.setData(self._command, FindIt.COMMAND_ROLE)
        self._model.appendRow(item)
    
    def removeRow(self, file_):
        """Removes the file item from the model"""
        item = self._model.findItems(file_.name)
        if item:
            self._model.takeRow(item[0].row())
            del item[0]
    
    def on_created(self, event):
        """Adds an item to the model if it is a file and matches the mask"""
        if not event.is_directory:
            if self._mask and not fnmatch.filter(event.src_path, self._mask):
                return
            
            file_ = path.path(event.src_path)
            self.addRow(file_)
    
    def on_deleted(self, event):
        """Removes an item from the model if it is a file and matches the mask"""
        if not event.is_directory:
            if self._mask and not fnmatch.filter(event.src_path, self._mask):
                return
            
            file_ = path.path(event.src_path)
            self.removeRow(file_)
    
    def on_moved(self, event):
        """Updates the model if it is a file and matches the mask"""
        if not event.is_directory:
            if self._mask and not fnmatch.filter(event.src_path, self._mask):
                return
            
            file_ = path.path(event.src_path)
            self.removeRow(file_)
            file_ = path.path(event.dest_path)
            self.addRow(file_)


class FindItThread(QtCore.QThread):
    """Thread to populate the initial file list"""
    fileAdded = QtCore.pyqtSignal(list)
    def __init__(self, root, mask, *args):
        super(FindItThread, self).__init__(*args)
        
        self._root = root
        self._mask = mask
        self._queue = []
    
    def run(self):
        """Main event loop.  Sends signals of batched file paths"""
        for file_ in path.path(self._root).walkfiles(self._mask):
            if len(self._queue) < 1000:
                self._queue.append(file_)
            else:
                self.fileAdded.emit(self._queue)
                self._queue = []
        
        self.fileAdded.emit(self._queue)


class FindIt(QtGui.QMainWindow):
    FILE_ROLE = QtCore.Qt.UserRole + 1
    COMMAND_ROLE = FILE_ROLE + 1
    def __init__(self, root, command, mask=None, custom=None, parent=None):
        super(FindIt, self).__init__(parent)
        
        custom = custom or []
        movie = QtGui.QMovie('./loader.gif')
        
        self.resize(544, 0)
        centralwidget = QtGui.QWidget(self)
        layout = QtGui.QVBoxLayout(centralwidget)
        self.setCentralWidget(centralwidget)
        layout.setMargin(0)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet(MAIN_STYLE)
        
        self._label = QtGui.QLabel(self)
        self._label.setMovie(movie)
        self._label.move(self.width() - 24, 0)
        
        self._lineedit = QtGui.QLineEdit(self)
        self._completer = QtGui.QCompleter(self)
        self._model = QtGui.QStandardItemModel(self)
        view = QtGui.QListView(self)
        view.setModel(self._model)
        self._root = path.path(root)
        self._command = command
        
        layout.addWidget(self._lineedit)
        layout.addWidget(view)
        
        self._completer.setModel(self._model)
        self._completer.setPopup(view)
        self._completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        view.setItemDelegate(FindItDelegate(self._lineedit, len(self._root)))
        self._lineedit.setCompleter(self._completer)
        self._lineedit.setEnabled(False)
        self._lineedit.setPlaceholderText('Gathering files...')
        self._lineedit.installEventFilter(FindItEventFilter(self))
        
        self._worker = FindItThread(root, mask)
        
        self.connect(self._completer, QtCore.SIGNAL('activated(const QModelIndex&)'), self.doit)
        self._worker.fileAdded.connect(self.addFile)
        self._worker.finished.connect(self.endGather)
        
        for cmd in custom:
            item = QtGui.QStandardItem('#%s' % cmd[0])
            item.setData(cmd[1], self.FILE_ROLE)
            item.setData(cmd[2], self.COMMAND_ROLE)
            self._model.appendRow(item)
        
        event_handler = FindItEvent(self._model, self._command, mask)
        self._observer = Observer()
        self._observer.schedule(event_handler, path=root, recursive=True)
        self._observer.start()
        movie.start()
        self._worker.start()
    
    def hideEvent(self, event):
        """Override of hideEvent, makes sure we stop the watchdog thread(s)"""
        self._observer.stop()
        return super(FindIt, self).hideEvent(event)
    
    def doit(self, index):
        """Handles executing the proper function based on item selection"""
        self.close()
        obj = index.data(self.COMMAND_ROLE)
        if obj == self._command:
            obj(str(index.data(self.FILE_ROLE)))
        else:
            ## -- Custom function string
            exec(str(obj), globals())
    
    def keyReleaseEvent(self, e):
        """Closes if the user hits escape"""
        if e.key() == QtCore.Qt.Key_Escape:
            self.close()
    
    def addFile(self, files):
        """Handler for initial file gatherinng thread.  Adds items to the model"""
        for file_ in files:
            item = QtGui.QStandardItem(file_.name)
            item.setData(str(file_), self.FILE_ROLE)
            item.setData(self._command, self.COMMAND_ROLE)
            self._model.appendRow(item)
    
    def endGather(self):
        """Ends the gathering phase and sets up the UI for the user"""
        self._label.deleteLater()
        self._lineedit.setEnabled(True)
        self._lineedit.setPlaceholderText('')
        self._lineedit.setFocus()


class FindItEventFilter(QtCore.QObject):
    """A Simple event filter to close the window when focus is lost"""
    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.FocusOut:
            self.parent().close()
            return True
        else:
            return QtCore.QObject.eventFilter(self, obj, event)


def func(filepath):
    """Test function for demo"""
    os.system('"%s"' % filepath)

def main():
    app = QtGui.QApplication(sys.argv)
    
    win = FindIt('.', func, '*.jpg', [('mycmd', 'some description', 'from pprint import pprint;pprint("xxx")')])
    win.show()
    
    sys.exit(app.exec_())

    
if __name__ == '__main__':
    main()