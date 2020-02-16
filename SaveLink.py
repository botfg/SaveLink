import getpass
import os
import sys
from datetime import date, datetime
import configparser

from pysqlcipher3 import dbapi2 as sqlcipher
import numpy


class color:
    OKBLUE = ('\033[94m')
    OKGREEN = ('\033[92m')
    WARNING = ('\033[93m')
    RED = ('\033[91m')
    END = ('\033[0m')


botslPrompt = (color.OKGREEN + "sl ~# " + color.END)


botslLogo = (color.OKGREEN + """
 ___                _    ___      _   
/ __|__ ___ _____  | |  |_ _|_ _ | |__
\__ / _` \ V / -_) | |__ | || ' \| / /
|___\____|\_/\___| |____|___|_||_|_\_\ \n""" + color.END)


def clearScr() -> None:
    os.system('clear')


def dec(string: str) -> str:
    length_string = (48 - len(string)) // 2     # 39
    decor = str((length_string * '-') + string + (length_string * '-') + '\n')
    return decor


def vhod():
    global account_pass, conn, cursor
    clearScr()
    x1 = os.path.isfile('main.db')
    if x1:
        name_db = ('main.db')
        conn = sqlcipher.connect(name_db)
        cursor = conn.cursor()
        clearScr()
        print(botslLogo)
        print(dec(color.RED + 'Sign in' + color.END))
        while True:
                try:
                    account_pass = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                    if account_pass == 'Q':
                        vhod()
                    cursor.execute("PRAGMA key={}".format(account_pass))
                    cursor.execute('SELECT COUNT(link) FROM links')
                except:
                    print(color.RED + 'wrong password' + color.END)
                else:
                    break
    elif not x1:
        print(botslLogo)
        print(dec(color.RED + 'Sign up' + color.END))
        while True:
            password1 = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
            if password1 == 'Q':
                vhod()
            else:
                break
        while True:
            password2 = getpass.getpass(color.OKBLUE + 'repeat password: ' + color.END)
            if password2 == 'Q':
                vhod()
            else:
                break
        while True:
            if password1 == password2:
                account_pass = password1
                break
            elif password1 != password2:
                print(color.RED + 'different passwords' + color.END)
                password1 = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                password2 = getpass.getpass(color.OKBLUE + 'repeat password: ' + color.END)
                if password1 or password2 == 'Q':
                    vhod()
        while True:
                u_podtver = input(color.OKBLUE + '[Y/n] add ' + color.END)
                if u_podtver == 'n':
                    vhod()
                    break
                elif u_podtver == 'Y':
                    # make users db
                    name_db = ('main.db')
                    conn = sqlcipher.connect(name_db)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA key={}".format(account_pass))
                    cursor.execute("""CREATE TABLE links
                        (id integer primary key, link varchar(255), info varchar(255), time datetime NOT NULL)
                            """)
                    conn.commit()
                    break
                    

def main():
    global account_pass, cursor, conn
    clearScr()
    print(botslLogo)
    print(dec(color.RED + 'options' + color.END))
    print(color.RED + '1' + color.END + ')--' + color.OKBLUE + 'Add' + color.OKBLUE)
    print(color.RED + '2' + color.END + ')--' + color.OKBLUE + 'View' + color.END)
    print(color.RED + '3' + color.END + ')--' + color.OKBLUE + 'Etc' + color.END)
    print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Settings' + color.OKBLUE)
    print(color.RED + '5' + color.END + ')--' + color.OKBLUE + 'Exit\n' + color.END)
    usercomand = input(botslPrompt)
    clearScr()
    if usercomand == '1':
        clearScr()
        print(botslLogo)
        print(dec(color.RED + 'Add' + color.END))
        while True:
            link = input(color.OKBLUE + 'enter the link: ' + color.END)
            if link == "Q":
                main()
            if len(link) > 5:
                break
        while True:
            info = input(color.OKBLUE + 'enter info: ' + color.END)
            if info == "Q":
                main()
            if len(info) > 1:
                break
        while True:
            usercomand = input(color.OKBLUE + '[Y/n] add link: ' + color.END +  link + color.OKBLUE + ' info: ' + color.END + str(info) + ': ')            
            if usercomand == "Y":
                now = date.today()
                cursor.execute("PRAGMA key={}".format(account_pass))
                cursor.execute("insert into links(link, info, time) values (?, ?, ?)", (link, info, now))
                conn.commit()
                conn.close() 
                main()
                break
            elif usercomand == "n" or "Q":
                main()
                break
    elif usercomand == '2':
        clearScr()
        print(botslLogo)
        print(dec(color.RED + 'Links' + color.END))
        cursor.execute("PRAGMA key={}".format(account_pass))
        cursor.execute('select count(link) from links')
        all_link = cursor.fetchone()
        if all_link[0] == 0:
            print(color.RED + "no links" + color.END)
            while True:
                print(color.RED + 'Q)--GO BACK\n' + color.END)
                uc = input(botslPrompt)
                if uc == 'Q':
                    main()
                    break
        else:
            cursor.execute("PRAGMA key={}".format(account_pass))
            cursor.execute('select id, link, info, time from links')
            results = numpy.array(cursor.fetchall(), dtype=str)
            for i in results:
                print(color.OKBLUE + 'id: ' + color.END + i[0] + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
            while True:
                print(color.RED + 'Q)--GO BACK\n' + color.END)
                uc = input(botslPrompt)
                if uc == 'Q':
                    main()
                    break
    elif usercomand == '3':
        cursor.execute("PRAGMA key={}".format(account_pass))
        while True:
            clearScr()
            print(botslLogo)
            print(dec(color.RED + 'Etc' + color.END))
            print(color.RED + '1' + color.END + ')--' + color.OKBLUE + 'Search' + color.OKBLUE)
            print(color.RED + '2' + color.END + ')--' + color.OKBLUE + 'Delete everything' + color.END)
            print(color.RED + '3' + color.END + ')--' + color.OKBLUE + 'Edit' + color.OKBLUE)
            print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Exit\n' + color.END)
            usercomand = input(botslPrompt)
            if usercomand == '1':
                clearScr()
                print('Search\n')
                cursor.execute('select count(link) from links')
                all_link = cursor.fetchone()
                if all_link[0] == 0:
                    print("no links")
                    while True:
                        print(color.RED + '\nQ)--GO BACK\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Q':
                            main()
                            break
                else:
                    cursor.execute("PRAGMA key={}".format(account_pass))
                    cursor.execute('select id, link, info, time from links')
                    results = numpy.array(cursor.fetchall(), dtype=str)
                    info_poisk = input('search word: \n')
                    if info_poisk == 'Q':
                        main()
                    for i in results:
                        if info_poisk in i[2]:
                            print('id: ' + i[0] + '\nlink: ' + i[1] + '\ninfo: ' + i[2] + '\ndata: ' + str(i[3]) + '\n')
                    while True:
                        print(color.RED + 'Q)--GO BACK\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Q':
                            main()
                            break
            elif usercomand == '2':
                clearScr()
                print('Delete all')
                while True:
                    try:
                        account_pass = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                        if account_pass == 'Q':
                            main()
                        cursor.execute("PRAGMA key={}".format(account_pass))
                        cursor.execute('SELECT COUNT(link) FROM links')
                    except:
                        print(color.RED + 'wrong password' + color.END)
                    else:
                        break        
                cursor.execute('DELETE FROM links')
                cursor.execute('REINDEX links')
                conn.commit()
                main()
            elif usercomand == '3':
                clearScr()
                print(botslLogo)
                print(dec(color.RED + 'Edit' + color.END))
                cursor.execute("PRAGMA key={}".format(account_pass))
                cursor.execute('select count(link) from links')
                all_link = cursor.fetchone()
                if all_link[0] == 0:
                    print(color.RED + "no links" + color.END)
                    while True:
                        print(color.RED + 'Q)--GO BACK\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Q':
                            main()
                            break
                else:
                    while True:
                        print(color.OKBLUE + 'show everyone? [Y/n]\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Y':
                            cursor.execute("PRAGMA key={}".format(account_pass))
                            cursor.execute('select id, link, info, time from links')
                            results = numpy.array(cursor.fetchall(), dtype=str)
                            for i in results:
                                print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
                            break
                        elif uc == 'n':
                            break
                        elif uc == 'Q':
                            main()
                            break
                    while True:
                        link_id = input(color.OKBLUE + 'id for edit: ' + color.END)
                        if link_id == 'Q':
                            main()
                        sql = ('SELECT COUNT(id) FROM links WHERE id = ?')
                        cursor.execute(sql, (link_id,))
                        results = cursor.fetchone()
                        if results[0] == 0:
                            print(color.RED + 'Id not found' + color.END)
                        elif results[0] == 1:
                            break
                    sql = ('SELECT * FROM links WHERE id = ?')
                    cursor.execute(sql, (link_id,))
                    i = cursor.fetchone()
                    clearScr()
                    print(botslLogo)
                    print(dec(color.RED + 'Edit' + color.END))
                    print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
                    while True:
                            print(color.RED + '1' + color.END + ')--' + color.OKBLUE + 'Remove' + color.OKBLUE)
                            print(color.RED + '2' + color.END + ')--' + color.OKBLUE + 'Change the link' + color.END)
                            print(color.RED + '3' + color.END + ')--' + color.OKBLUE + 'Change info' + color.OKBLUE)
                            print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Exit\n' + color.OKBLUE)
                            usercomand = input(botslPrompt)
                            if usercomand == '1':
                                clearScr()
                                print(botslPrompt)
                                print(dec(color.RED + 'Remove' + color.END))
                                usercomand = input(color.OKBLUE + '[Y/n] Remove: ' + color.END +  i[1] + color.OKBLUE + ' info: ' + color.END + [2] + ': ')            
                                if usercomand == "Y":
                                    sql = ("""DELETE FROM links WHERE id = ?""")
                                    cursor.execute(sql, (link_id,))
                                    conn.commit()
                                    main()
                                    break
                                elif usercomand == 'n' or 'Q':
                                    main()
                                    break
                            elif usercomand == '2':
                                clearScr()
                                print(botslPrompt)
                                print(dec(color.RED + 'Change the link' + color.END))
                                print(color.OKBLUE + '\nid: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
                                while True:
                                    new_link = input(color.OKBLUE + 'enter a new link: ' + color.END)
                                    usercomand = input(color.OKBLUE + '[Y/n] replace ' + color.END +  i[1]  + color.OKBLUE + ' on the ' + color.END + new_link + ': ')            
                                    if usercomand == "Y":
                                        sql = ("""UPDATE links SET link = ? WHERE id = ?""")
                                        cursor.execute(sql, (new_link, link_id))
                                        conn.commit()
                                        main()
                                        break
                                    elif usercomand == 'n' or 'Q':
                                        main()
                                        break                        
                            elif usercomand == '3':
                                clearScr()
                                print(botslPrompt)
                                print(dec(color.RED + 'Change info' + color.END))
                                print(color.OKBLUE + '\nid: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
                                while True:
                                    new_info = input(color.OKBLUE + 'enter new info: ' + color.END)
                                    usercomand = input(color.OKBLUE + '[Y/n] replace ' + color.END +  i[2]  + color.OKBLUE + ' on the ' + color.END + new_info + ': ')            
                                    if usercomand == "Y":
                                        sql = ("""UPDATE links SET info = ? WHERE id = ?""")
                                        cursor.execute(sql, (new_info, link_id))
                                        conn.commit()
                                        main()
                                        break
                                    elif usercomand == 'n' or 'Q':
                                        main()
                                        break  
                            elif usercomand == '4':
                                main()
                                break
            elif usercomand == '4':
                main()
                break
    elif usercomand == '4':
        pass
    elif usercomand == '5':
        clearScr()
        sys.exit()
    else:
        main()






if __name__ == "__main__":
    vhod()
    main()