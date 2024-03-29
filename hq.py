#from __future__ import unicode_literals
import Tkinter as tk, Tkconstants, tkFileDialog, tkMessageBox
import shutil
import os, errno
import glob
import datetime, time
import sqlite3 as q
import json

class Hq:
    def __init__(self, win, db):
        self.win = win  
        self.db = db
        self.win.title("Stage Files for HQ (v3)")
        self.paths     = {'src': '', 'dest': '' } #actual path
        self.locLabels = {'src': '', 'dest': '' } #Tkinter pointer
        self.text = [
            "Stage Files for HQ", 
            "This helpful app automates the transfering of modified files to HQ",
            "Files modified since the prior transfer will be moved to the Staging Folder.",
            "Select Source and Destination folders then click 'Move to Staging Folder'",
        ]
        # defining options for opening a directory
        self.dir_opt = self.options = {}
        self.options['initialdir'] = 'C:/'
        self.options['mustexist'] = False
        self.options['parent'] = win
        self.options['title'] = ''
        self.results = {'moved'  : [], 'skipped': [], 'lastXfer': None }
        self.__initMenu()
        self.__initWin()
        self.__setHistoryLabels()
        self.__getDbPaths()

    def __initMenu(self):
        # create a toplevel menu 
        menubar = tk.Menu(self.win) 
        # create a pulldown menu, and add it to the menu bar 
        filemenu    = tk.Menu(menubar, tearoff=False)
        reportmenu  = tk.Menu(menubar, tearoff=False) 
        exitmenu    = tk.Menu(menubar, tearoff=False)
        filemenu.add_command(label='Select Source Folder'       , command= lambda: self.setFolder('src')) 
        filemenu.add_command(label='Select Destination Folder'  , command= lambda: self.setFolder('dest')) 
        filemenu.add_separator() 
        filemenu.add_command(label='Exit'                                  , command=self.win.destroy) 
        reportmenu.add_command(label='Results of last 10 Transfers'        , command=self.showXfers) 
        reportmenu.add_command(label='List files included in last transfer', command=self.showHistory) 
        exitmenu.add_command(label='About'                                 , command=self.aboutBox) 
        menubar.add_cascade(menu=filemenu, label='File') 
        menubar.add_cascade(menu=reportmenu, label='Reports') 
        menubar.add_cascade(menu=exitmenu, label='Help') 
        self.win.config(menu=menubar) 

    def __initWin(self):
       
        self.headImage = tk.PhotoImage(file="header.gif")
        self.headImage = self.headImage.subsample(2,3)

        tk.Label(self.win, text = self.text[0], font = ('Arial', 42, 'bold'), pady=10, anchor='s', compound="center", fg='white', image=self.headImage).pack()
        tk.Frame(self.win, height = 1).pack()
        tk.Label(self.win, text = self.text[1], font = ('Arial', 10)).pack()
        tk.Label(self.win, text = self.text[2], font = ('Arial', 10), padx = 20).pack()
        tk.Label(self.win, text = self.text[3], font = ('Arial', 10)).pack()
        tk.Frame(self.win, height = 10).pack()

    #create button container frame
        self.con1 = tk.Frame(self.win, height=50, width = 300, padx=100, pady=0, bd=3, relief='groove' )
        self.con1.pack()

    # define button
        self.b1Image = tk.PhotoImage(file="icon-arrow-l.gif")
        self.b1Image = self.b1Image.subsample(4,4)
        tk.Frame(self.con1, height = 15).pack()
        self.bSource = tk.Button(self.con1, width=250, font = ('Calibri', 14), text='  Source Folder', command= lambda: self.setFolder('src'), image=self.b1Image, compound="left", pady=2, padx=20)
        self.bSource.pack() 
        self.locLabels['src'] = tk.Label(self.con1, pady=10, text = os.path.normpath(self.paths['src']))
        self.locLabels['src'].pack()
        tk.Frame(self.win, height = 15).pack()
    
    #create button container frame    
        self.con2 = tk.Frame(self.win, height=20, width = 300, padx=100, pady=0, bd=3, relief='groove' )
        self.con2.pack()

    # define button
        self.b2Image = tk.PhotoImage(file="icon-arrow-r.gif")
        self.b2Image = self.b2Image.subsample(4,4)
        tk.Frame(self.con2, height = 15).pack()
        self.bDest = tk.Button(self.con2, width=250, font = ('Calibri', 14), text='  Destination Folder', command= lambda: self.setFolder('dest'), image=self.b2Image, compound="left", pady=2, padx=20)
        self.bDest.pack()
        self.locLabels['dest'] = tk.Label(self.con2, pady=10,text = os.path.normpath(self.paths['dest'])) 
        self.locLabels['dest'].pack()
        tk.Frame(self.win, height = 15).pack()

    # define button
        self.bImage = tk.PhotoImage(file="upload.gif")
        self.bImage = self.bImage.subsample(2,2)
        self.bCopy   = tk.Button(self.win, width=200, font = ('Calibri', 14), state='normal' if self.__okToCopy() else 'disabled', text='Move to\nStaging Folder', pady = 10, command=self.moveFiles, image=self.bImage, compound="right")
        self.bCopy.pack() #**self.button_opt)
        tk.Frame(self.win, height = 15).pack()

        self.con3 = tk.Frame(self.win, height=20, width = 260, padx=40, pady=0, bd=2, relief='groove' )
        self.con3.pack()
        tk.Frame(self.con3, height = 10).pack()
        self.xferLabel = tk.Label(self.con3, font = ('Arial', 10, 'bold'), text = 'Last Transfer Completed: {}'.format(self.results['lastXfer']))
        self.xferLabel.pack()
        self.xferMove = tk.Label(self.con3, text = 'Files Moved Last Transfer:{}'.format(len(self.results['moved'])))
        self.xferMove.pack()
        self.xferSkip = tk.Label(self.con3, text = 'Files Skipped Last Transfer:{}'.format(len(self.results['skipped'])))
        self.xferSkip.pack()
        tk.Frame(self.con3, height = 10).pack()

        tk.Frame(self.win, height = 5).pack()
    
    def showHistory(self):
        h = self.db.dbConfig['hqTables'][1] #hq_history
        r = self.db.dbConfig['hqTables'][2] #hq_results

        if self.db.emptyTable(r):
            tkMessageBox.showinfo( "No Data", "No transfers to report." )       
        else:
            query = "SELECT r.filename FROM {0} r INNER JOIN {1} h ON r.move_date = h.move_date WHERE (SELECT MAX(h.move_date) FROM {1} h) = r.move_date".format(r, h)
            rows = self.db.q(query) 

            if len(rows) == 0:
                msg = 'No files moved in last transfer.\nRun Last 10 report for results of last transfer.'
            else:
                msg = self.db.reportLastFiles(rows)
    
            tkMessageBox.showinfo( "Files moved in Last Batch", msg )       

    def showXfers(self):
        dbHist = self.db.dbConfig['hqTables'][1]
        if self.db.emptyTable(dbHist):
            tkMessageBox.showinfo( "No Data", "No transfers to report." )       
        else:
            rows = self.db.q('SELECT move_date, moved, failed, skipped FROM {0} WHERE hq_id = {1} ORDER BY move_date DESC LIMIT 10'.format( dbHist, self.db.hq_id)) 
            msg = self.db.reportLast10(rows)
            tkMessageBox.showinfo( "Summary of last 10 Transfers", msg )       

    def aboutBox(self):
        tkMessageBox.showinfo( "About", "Stage files for HQ.\n\n© 2016 HQ Inc." )       

    def __okToCopy(self):
        if self.paths["src"] != '' and self.paths["dest"] != '' and self.paths["src"] != self.paths["dest"]:
            return True
        else:
            if self.paths["src"] == self.paths["dest"]:
                #self.paths["src"] will be '' if new tables
                if self.paths["src"] != '':
                    tkMessageBox.showerror( "Error", "Source and destination can't be the same folder.\nChange source or destination folder." )
            return False

    def __setHistoryLabels(self):
        #update the last transfer data and stats if there are records in the table
        if not self.db.emptyTable(self.db.dbConfig['hqTables'][1]):
            rows = self.db.q('SELECT move_date, moved, failed, skipped FROM {0} WHERE move_date = (SELECT MAX(move_date) FROM {0}) AND hq_id = {1}'.format(self.db.dbConfig['hqTables'][1], self.db.hq_id)) 
            assert len(rows) is 1, "Didn't receive exactly one item back."
            xferDate, moved, failed, skipped = rows[0]

            self.xferLabel.config(text = 'Last Transfer Completed: {}'.format( xferDate.strftime( "%b %d, %Y at %H:%M:%S")) )
            self.xferMove.config(text = 'Files Moved Last Transfer:  {}'.format( moved ))
            self.xferSkip.config(text = 'Files Skipped Last Transfer: {}'.format( skipped ))

    def setFolder(self,loc):
        #called when the user clicks button to set the source or destination folder
        self.dir_opt['title'] = 'Select the SOURCE directory' if (loc=='src') else 'Select the DESTINATION directory'
        path = tkFileDialog.askdirectory(**self.dir_opt)
        if path:
            #if a valid path is returned | else don't change anything
            self.paths[loc] = path
            self.__setPathLabel(loc)
            sqlStmt = r"UPDATE {} SET {}_dir = '{}' WHERE hq_id = {}".format(self.db.dbConfig['hqTables'][0], loc, self.paths[loc], self.db.hq_id)
            self.db.x(sqlStmt)

        self.bCopy['state'] = 'normal' if self.__okToCopy() else 'disabled'

    def __getDbPaths(self):
        for loc in self.locLabels:
            rows = self.db.q('SELECT {}_dir FROM hq_data WHERE hq_id = {}'.format(loc, self.db.hq_id))
            assert len(rows) is 1, "Didn't receive exactly one item back."
            
            try:
                self.paths[loc] = rows[0][0] if os.path.isdir( rows[0][0] ) else os.path.normpath('C:/')
                self.__setPathLabel(loc)
            except:
                print('Error retrieving saved folder. Setting to root.')
                self.paths[loc] = os.path.normpath('C:/')
        
        if not self.db.newTables:
            self.bCopy['state'] = 'normal' if self.__okToCopy() else 'disabled'
            self.db.newTables = False

    def __setPathLabel(self,loc):
        #Updates the label passed as 'loc' with the currently selected path 
        self.locLabels[loc].config(text = (self.paths[loc]))    
        self.locLabels[loc].config(text = os.path.normpath(self.paths[loc]) )

    def __showResults(self,m,c):
        #display the results of the file copy
        tkMessageBox.showinfo( "Summary", "{} files moved and {} files skipped.\nSee console for details.".format(m, c) )

    def __edited(self, f):
        return True if ( datetime.datetime.fromtimestamp( os.path.getmtime(f) ) > self.results['lastXfer'] ) else False

    def moveFiles(self):
        #copy ALL .txt files MODIFIED/CREATED since last move from Folder "src" to Folder "dest"
        file_filter = "*.txt"
        cutoff = datetime.datetime.now()
        #if no prior transfer, set datetime to now
        if self.results['lastXfer'] == None:
            self.results['lastXfer'] = cutoff
    
        #holding the list allows for extensibility in recording files transfered
        moved = []
        skipped = []
        
        try:
            for file_ in glob.glob(self.paths["src"]+"/"+file_filter):

                if self.__edited(file_):
                    editTime = datetime.datetime.fromtimestamp( int(os.path.getmtime(file_)) ).strftime("%b %d-%y %H:%M:%S")
                    #editTime = datetime.datetime.fromtimestamp(os.path.getmtime(file_))
                    #print("edit time") ; print(editTime)

                    shutil.move( file_, self.paths["dest"] )
                    print( '{} modified at {}.\n-->Moving to batch folder "{}"'.format(file_, editTime, self.paths["dest"]) )
                    moved.append( file_ )
                else:
                    print( "{} not new/modified...skipping".format(file_) )
                    skipped.append( file_ )

        except IOError as err:
            print("I/O Error ({}) moving {}.".format(err,file_))
            pass

        except Exception as err:
            print("{} moving {}".format(err,file_))
            pass

        self.__saveXfer(cutoff, moved, skipped)

    def __saveXfer(self, cutoff, moved, skipped):
        sqlStmt = r"UPDATE {} SET last_move = '{}' WHERE hq_id = {}".format(self.db.dbConfig['hqTables'][0], cutoff, self.db.hq_id)
        self.db.x(sqlStmt)

        sqlStmt = r"INSERT INTO {} VALUES (?,?,?,?,?)".format(self.db.dbConfig['hqTables'][1]) #hq_history
        values = (self.db.hq_id, cutoff, len(moved), 0, len(skipped))
        self.db.x(sqlStmt, values)

        for filename in moved:
            sqlStmt = r"INSERT INTO {} VALUES (?,?,?)".format(self.db.dbConfig['hqTables'][2]) #hq_results
            values = (self.db.hq_id, cutoff, filename )
            self.db.x(sqlStmt, values)
        
        self.__showResults(len(moved), len(skipped))
        self.__setHistoryLabels() 
        self.results["moved"] = moved
        self.results["skipped"] = skipped

class Db:
    def __init__(self, hq_id):
        self.hq_id = hq_id
        #dict that shared data with hq.json
        self.dbConfig = {}
        self.newTables = False
        self.dbConfig['configFile'] = 'hq.json'
        #name and path are default values that will be used if hq.json is not found or is corrupt
        self.dbConfig['dbName']     = 'hq.db'
        self.dbConfig['dbPath']     = ''
        self.dbConfig['hqTables']   = ['hq_data', 'hq_history', 'hq_results']
        #TO SET a field to TYPE=TIMESTAMP you also must INCLUDE detect_types=q.PARSE_DECLTYPES in the database connection command
        self.dbConfig['hqFields']   = [
            'hq_id INTEGER PRIMARY KEY, src_dir TEXT NOT NULL, dest_dir TEXT NOT NULL, last_move TIMESTAMP',
            'hq_id INTEGER, move_date TIMESTAMP PRIMARY KEY, moved INTEGER, failed INTEGER, skipped INTEGER, FOREIGN KEY(hq_id) REFERENCES {}(hq_id)'.format(self.dbConfig['hqTables'][0]),
            'hq_id INTEGER, move_date TIMESTAMP NOT NULL, filename TEXT, FOREIGN KEY(move_date) REFERENCES {}(move_date)'.format(self.dbConfig['hqTables'][1]),
            ]
        #concatenated path+db_name
        self.hqdb = self.dbConfig['dbPath']+self.dbConfig['dbName']

        self.prepDb()

    def q(self, sqlStmt):
        # q=query utility method
        cursor = self.con.cursor()
        cursor.execute(sqlStmt)
        result = cursor.fetchall()
        cursor.close()
        return result

    def x(self, sqlStmt, values=()):
        # x=execute utility method
        cursor = self.con.cursor()
        cursor.execute(sqlStmt, values) if values else cursor.execute(sqlStmt)
        self.con.commit()
        cursor.close()

    def emptyTable(self, table):
        #utility method
        #returns true if passed table is empty 
        query = 'SELECT COUNT(*) FROM {} LIMIT 1'.format(table)
        x = self.q(query)
        return x[0][0] == 0

    def reportLast10(self,results):
        parsed = ''
        for rec in results:
            d, m, f, s = rec
            parsed += 'Date: {} | Moved: {} | Failed: {} | Skipped: {}\n'.format( d.strftime( "%b %d, %Y at  %H:%M:%S"), m, f, s ) 
        return parsed

    def reportLastFiles(self,results):
        parsed = ''
        for rec in results:
            f = str(rec)
            parsed += '{}\n'.format( os.path.normpath(f) ) 
        return parsed

    def prepDb(self):
        try:
            with open(self.dbConfig['configFile']) as file:
                hq_json = json.load(file)
                self.dbConfig['dbName'] = hq_json['dbName']
                self.dbConfig['dbPath'] = hq_json['dbPath']

        except IOError as e:
            tkMessageBox.showerror( "File Error", "Error opening {0}.\n Creating {0} and using defaults.".format(self.dbConfig['configFile']) )
            #Does not exist OR no read permissions
            print "Error opening {} to open file".format(self.dbConfig['configFile']) 
            
            with open(self.dbConfig['configFile'], 'w') as newDbFile:
                json.dump(self.dbConfig, newDbFile)
        self.verifyDb() 

    def verifyDb(self):
        try:
            #create database directory or fail pythonically if the path exists
            #if dbPath in JSON is '' then db is expected in the program root
            #if a path is provided in the JSON it must indlude the trailing / 
            if self.dbConfig['dbPath']:
                os.makedirs(self.dbConfig['dbPath'])

        except OSError as exception:
            #if the exception *isn't* that the directory exists, raise a real exception
            if exception.errno != errno.EEXIST:
                raise
            #if (not self.dbConfig['dbPath']) or not self.dbConfig['dbPath'].endswith('/'):
            if (not self.dbConfig['dbPath']) or (not self.dbConfig['dbPath'].endswith('/')):
                print("Path in db.json is not formatted correctly.\nPath should be '' for root or end with a slash e.g. data/")
                raise #Exception("Path in db.json is not formatted correctly.\nPath should be '' for root or end with a slash e.g. data/")

        self.hqdb = self.dbConfig['dbPath']+self.dbConfig['dbName']

        with q.connect(self.hqdb, detect_types=q.PARSE_DECLTYPES) as self.con:
            self.con.text_factory = str
            self.verifyTables()
            if self.emptyTable(self.dbConfig['hqTables'][0]):
                print( 'no records...populating table')
                self.populateTables()
                #assume tables are new
                self.newTables = True

    def verifyTables(self):
        #create tables if they don't exist
        for i in range(len(self.dbConfig['hqTables'])):
            #self.c.execute('CREATE TABLE IF NOT EXISTS {}({})'.format(self.dbConfig['hqTables'][i],self.dbConfig['hqFields'][i]) )
            sqlStmt = 'CREATE TABLE IF NOT EXISTS {}({})'.format(self.dbConfig['hqTables'][i],self.dbConfig['hqFields'][i]) 
            self.x(sqlStmt)

    def populateTables(self):
        hqDataVals = [self.hq_id, "C:/", "C:/", None]
        sqlStmt = 'INSERT INTO {} VALUES (?,?,?,?)'.format(self.dbConfig['hqTables'][0])
        values = (hqDataVals[0],hqDataVals[1],hqDataVals[2],hqDataVals[3],)
        self.x(sqlStmt, values)
        print('Created new tables and added default data') 

def centerRoot(root):
    w = 600 # width for the Tk root
    h = 680 # height for the Tk root
    ws = root.winfo_screenwidth() # width of the screen
    hs = root.winfo_screenheight() # height of the screen
    # calculate x and y coordinates for the Tk root window
    x = (ws/2) - (w/2)
    y = (hs/2) - (h/2)
    # set the dimensions of the screen and where it is placed
    root.geometry('%dx%d+%d+%d' % (w, h, x, y))

def main():
    root = tk.Tk()
    centerRoot(root)
    db = Db(100)
    win = Hq(root, db)

    root.mainloop()

if __name__ == "__main__": main()    