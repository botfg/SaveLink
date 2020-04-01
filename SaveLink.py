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


db_dir = ('/home/{}/.savelink/'.format(getpass.getuser()))


papka = os.path.isdir(db_dir)
if papka == False:
    os.mkdir(db_dir)


botslLogo = (color.OKGREEN + r"""
 ___                _    ___      _   
/ __|__ ___ _____  | |  |_ _|_ _ | |__
\__ / _` \ V / -_) | |__ | || ' \| / /
|___\____|\_/\___| |____|___|_||_|_\_\ """ + color.END)


def clearScr() -> None:
    os.system('clear')


def dec(string: str) -> str:
    length_string = (48 - len(string)) // 2     # 39
    decor = str((length_string * '-') + string + (length_string * '-') + '\n')
    return decor


def vhod():
    global account_pass, conn, cursor
    clearScr()
    x1 = os.path.isfile(db_dir + 'main.db')
    if x1:
        name_db = (db_dir + 'main.db')
        conn = sqlcipher.connect(name_db)
        cursor = conn.cursor()
        clearScr()
        print(botslLogo)
        print(dec(color.RED + 'Sign in' + color.END))
        while True:
                try:
                    account_pass = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                    if account_pass == 'Q':
                        clearScr()
                        sys.exit()
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
                clearScr()
                sys.exit()
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
                    name_db = (db_dir + 'main.db')
                    conn = sqlcipher.connect(name_db)
                    cursor = conn.cursor()
                    cursor.execute("PRAGMA key={}".format(account_pass))
                    cursor.execute("""CREATE TABLE links
                        (id integer primary key, link varchar(255), info varchar(255), category varchar(255), time datetime NOT NULL)
                            """)
                    conn.commit()
                    break
                    

def main():
    global account_pass, cursor, conn
    clearScr()
    cursor.execute("PRAGMA key={}".format(account_pass))
    cursor.execute('select count(link) from links')
    all_link = cursor.fetchone()
    cursor.execute('select category from links GROUP BY category')
    all_category = numpy.array(cursor.fetchall(), dtype=str) 
    print(botslLogo)
    print(dec(color.RED + 'options' + color.END))
    print(color.RED + '1' + color.END + ')--' + color.OKBLUE + 'Add' + color.END)
    print(color.RED + '2' + color.END + ')--' + color.OKBLUE + 'View' + color.END + '(' + str(all_link[0]) + ')')
    print(color.RED + '3' + color.END + ')--' + color.OKBLUE + 'Etc' + color.END)
    print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Categories' + color.END + '(' + str(all_category.size) + ')')
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
            cursor.execute("PRAGMA key={}".format(account_pass))
            cursor.execute('select category from links')
            results = numpy.array(cursor.fetchall(), dtype=str)
            if results.size > 0:
                category_str = ""
                for i in results:
                    category_str += str(i[0] + ', ')
                print(color.OKBLUE + "categories: " + color.END + category_str[:-2])
            category = input(color.OKBLUE + 'enter category: ' + color.END)
            if len(category) == 0:
                print(color.RED + 'wrong category' + color.RED)
            if category == 'Q':
                main()
            if len(category) > 0:
                break
        while True:
            usercomand = input(color.OKBLUE + '[Y/n] add link: ' + color.END +  link + color.OKBLUE + ' info: ' + color.END + info + color.OKBLUE + ' category: ' + color.END + category +': ')            
            if usercomand == "Y":
                now = date.today()
                cursor.execute("PRAGMA key={}".format(account_pass))
                cursor.execute("insert into links(link, info, time, category) values (?, ?, ?, ?)", (link, info, now, category))
                conn.commit() 
                main()
                break
            elif usercomand == "n" or "Q":
                main()
                break
    elif usercomand == '2':
        clearScr()
        print(botslLogo)
        print(dec(color.RED + 'Links' + color.END))
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
            cursor.execute('select id, link, info, time, category from links')
            results = numpy.array(cursor.fetchall(), dtype=str)
            for i in results:
                print(color.OKBLUE + 'id: ' + color.END + i[0] + color.OKBLUE +  
                      '\nlink: ' + color.END + i[1] + color.OKBLUE + 
                      '\ninfo: ' + color.END + i[2] + color.OKBLUE + 
                      '\ncategory: ' + color.END + i[4] + color.OKBLUE + 
                      '\ndata: ' + color.END + i[3] + color.OKBLUE + '\n')
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
            print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Remove account' + color.OKBLUE)
            print(color.RED + '5' + color.END + ')--' + color.OKBLUE + 'Exit\n' + color.END)
            usercomand = input(botslPrompt)
            if usercomand == '1':
                clearScr()
                print(botslLogo)
                print(dec(color.RED + 'Search' + color.END))
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
                    cursor.execute('select id, link, info, time, category from links')
                    results = numpy.array(cursor.fetchall(), dtype=str)
                    info_poisk = input(color.OKBLUE + 'search word: ' + color.END)
                    print("")
                    if info_poisk == 'Q':
                        main()
                    for i in results:
                        if info_poisk in i[2] or info_poisk in i[4]:
                            print(color.OKBLUE + 'id: ' + color.END + i[0] + color.OKBLUE +  
                                '\nlink: ' + color.END + i[1] + color.OKBLUE + 
                                '\ninfo: ' + color.END + i[2] + color.OKBLUE + 
                                '\ncategory: ' + color.END + i[4] + color.OKBLUE + 
                                '\ndata: ' + color.END + i[3] + color.OKBLUE + '\n')                            
                    while True:
                        print(color.RED + 'Q)--GO BACK\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Q':
                            main()
                            break
            elif usercomand == '2':
                clearScr()
                print(botslLogo)
                print(dec(color.RED + 'Delete all' + color.END))
                while True:
                    account_password = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                    if account_password == 'Q':
                        main()
                    if account_pass == account_password:
                        break
                    if account_password != account_pass:
                        print(color.RED + 'wrong password' + color.END)        
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
                            cursor.execute('select id, link, info, time, category from links')
                            results = numpy.array(cursor.fetchall(), dtype=str)
                            print("")
                            for i in results:
                                print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE  + '\ncategory: ' + color.END + i[4] + color.OKBLUE + '\ndata: ' + color.END + str(i[3]) + '\n')
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
                    print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ncategory: ' + color.END + i[3] + color.OKBLUE + '\ndata: ' + color.END + str(i[4]) + '\n')
                    while True:
                            print(color.RED + '1' + color.END + ')--' + color.OKBLUE + 'Remove' + color.OKBLUE)
                            print(color.RED + '2' + color.END + ')--' + color.OKBLUE + 'Change the link' + color.END)
                            print(color.RED + '3' + color.END + ')--' + color.OKBLUE + 'Change info' + color.OKBLUE)
                            print(color.RED + '4' + color.END + ')--' + color.OKBLUE + 'Change category' + color.OKBLUE)
                            print(color.RED + '5' + color.END + ')--' + color.OKBLUE + 'Exit\n' + color.OKBLUE)
                            usercomand = input(botslPrompt)
                            if usercomand == '1':
                                clearScr()
                                print(botslLogo)
                                print(dec(color.RED + 'Remove' + color.END))
                                usercomand = input(color.OKBLUE + '[Y/n] Remove: ' + color.END +  str(i[1]) + color.OKBLUE + ' info: ' + color.END + i[2] + ': ')            
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
                                print(botslLogo)
                                print(dec(color.RED + 'Change the link' + color.END))
                                print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE  + '\ncategory: ' + color.END + i[3] + color.OKBLUE + '\ndata: ' + color.END + i[4] + '\n')
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
                                print(botslLogo)
                                print(dec(color.RED + 'Change info' + color.END))
                                print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE  + '\ncategory: ' + color.END + i[3] + color.OKBLUE + '\ndata: ' + color.END + i[4] + '\n')
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
                                clearScr()
                                print(botslLogo)
                                print(dec(color.RED + 'Change category' + color.END))
                                print(color.OKBLUE + 'id: ' + color.END + str(i[0]) + color.OKBLUE +  '\nlink: ' + color.END + i[1] + color.OKBLUE + '\ninfo: ' + color.END + i[2] + color.OKBLUE + '\ncategory: ' + color.END + i[3] + color.OKBLUE + '\ndata: ' + color.END + i[4] + '\n')
                                while True:
                                    new_category = input(color.OKBLUE + 'enter new category: ' + color.END)
                                    usercomand = input(color.OKBLUE + '[Y/n] replace ' + color.END +  i[3]  + color.OKBLUE + ' on the ' + color.END + new_category + ': ')            
                                    if usercomand == "Y":
                                        sql = ("""UPDATE links SET category = ? WHERE id = ?""")
                                        cursor.execute(sql, (new_category, link_id))
                                        conn.commit()
                                        main()
                                        break
                                    elif usercomand == 'n' or 'Q':
                                        main()
                                        break 
                            elif usercomand == '5':
                                main()
                                break
            elif usercomand == '4':
                clearScr()
                print(botslLogo)
                print(dec(color.RED + 'Remove account' + color.END))
                while True:
                    usercomand = input(color.OKBLUE + '[Y/n] Remove account? ')            
                    if usercomand == ('Q' or 'n'):
                        main()
                    if usercomand == 'Y':
                        break
                    else:
                        print(color.RED + 'wrong command' + color.END)
                while True:
                    account_password = getpass.getpass(color.OKBLUE + 'enter password: ' + color.END)
                    if account_password == 'Q':
                        main()
                    if account_pass == account_password:
                        break
                    if account_password != account_pass:
                        print(color.RED + 'wrong password' + color.END) 
                cursor.close()
                conn.close()
                os.remove(db_dir + 'main.db')
                vhod()
                main()
            elif usercomand == '5':
                main()
                break
    elif usercomand == '4':
        while True:
            clearScr()
            print(botslLogo)
            print(dec(color.RED + 'Categories' + color.END))
            cursor.execute("PRAGMA key={}".format(account_pass))
            cursor.execute('select category from links GROUP BY category')
            if all_link[0] == 0:
                print(color.RED + "no links" + color.END)
                while True:
                    print(color.RED + 'Q)--GO BACK\n' + color.END)
                    uc = input(botslPrompt)
                    if uc == 'Q':
                        main()
                        break
            else:        
                results = numpy.array(cursor.fetchall(), dtype=str) 
                item_uc = {j:i[0] for i,j in zip(results,[i + 1 for i in range(len(results))])}   
                for i in item_uc:
                    print(color.RED + str(i) + color.END + ')--' + color.OKBLUE + item_uc[i] + color.OKBLUE)
                print(color.RED + str(i + 1) + color.END + ')--' + color.OKBLUE + 'Exit' + color.OKBLUE)
                usercomand = input('\n' + botslPrompt)
                if usercomand == "Q":
                    main()
                    break
                elif usercomand == str(i + 1):
                    main()
                try:
                    while True:
                        clearScr()
                        print(botslLogo)
                        print(dec(color.RED + 'Categories: ' + color.END + item_uc[int(usercomand)]))
                        cursor.execute("PRAGMA key={}".format(account_pass))
                        sql = ('select * from links where category = ?')
                        cursor.execute(sql, (item_uc[int(usercomand)],))
                        results = numpy.array(cursor.fetchall(), dtype=str) 
                        for i in results:
                            print(color.OKBLUE + 'id: ' + color.END + i[0] + color.OKBLUE +  
                                '\nlink: ' + color.END + i[1] + color.OKBLUE + 
                                '\ninfo: ' + color.END + i[2] + color.OKBLUE + 
                                '\ncategory: ' + color.END + i[3] + color.OKBLUE + 
                                '\ndata: ' + color.END + i[4] + color.OKBLUE + '\n')
                        print(color.RED + 'Q)--GO BACK\n' + color.END)
                        uc = input(botslPrompt)
                        if uc == 'Q':
                            break
                except:
                    pass
                else:
                    main()
    elif usercomand == '5':
        clearScr()
        sys.exit()
    else:
        main()

vhod()        
main()