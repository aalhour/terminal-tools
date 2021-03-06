#!/usr/bin/env python
import os
import re
import json
import time
import errno
import shutil
import urllib
import urllib2
import tarfile
import argparse
import subprocess

bin_filename = 'pulldocker'
dockerhub_url = 'https://registry.hub.docker.com'
defaults = {'user':'root', 'entrypoint':'/entrypoint.sh ', 'cmd':'', 'wdir':'/root'}


def get_pulldocker_bin(filename):
    for path in os.environ["PATH"].split(":"):
        fullpath = '%s/%s'% (path, filename)
        if os.path.exists(fullpath):
            if os.path.isfile(fullpath):
                if os.access(fullpath,os.X_OK):
                    return fullpath
                else:
                    exit('Cannot execute %s. Check file permissions.'% fullpath)
            else:
                exit('%s is not a file.'% fullpath)
        else:
            pass
    print '%s not found in path, Trying to install it.'% filename
    install_pulldocker()
    return '/usr/local/bin/pulldocker'

def get_dockerfile_details(user, repo):
    raw_dockerfile = '%s/u/%s/%s/dockerfile/raw' % (dockerhub_url,user,repo)
    output = {}
    try:
        response = urllib2.urlopen(raw_dockerfile)
        dockerfile = response.read()
        dockerfile = dockerfile.replace('\\\n', ' ')
        f = [a[1] for a in re.findall(r'(FROM|from)\s+(.*)', dockerfile)][0]
        maintainer = [a[1] for a in re.findall(r'(MAINTAINER|maintainer)\s+(.*)', dockerfile)]
        lines = re.findall(r'\n(COPY|copy|ADD|add|RUN|run|WORKDIR|workdir|ENV|env)\s+(.*)', dockerfile)
        cmds = [a[1] for a in re.findall(r'\n(CMD|cmd)\s+(.*)', dockerfile)]
        envs = [a[1] for a in re.findall(r'\n(ENV|env)\s+(.*)', dockerfile)]
        volumes = [a[1] for a in re.findall(r'\n(volume|VOLUME)\s+(.*)', dockerfile)]
        wdir = [a[1] for a in re.findall(r'\n(workdir|WORKDIR)\s+(.*)', dockerfile)]
        ports = [a[1] for a in re.findall(r'\n(expose|EXPOSE)\s+(.*)', dockerfile)]
        duser = [a[1] for a in re.findall(r'\n(user|USER)\s+(.*)', dockerfile)]
        entrypoint = [a[1] for a in re.findall(r'\n(ENTRYPOINT|entrypoint)\s+(.*)', dockerfile)]
        output = {'FROM': f,
                 'lines': lines,
                 'ENV': envs,
                 'VOL': volumes,
                 'PORTS': ports}
        try:
            output['CMD'] = json.loads(cmds[0])
        except:
            output['CMD'] = cmds
        output['WDIR'] = wdir[0] if wdir != [] else None
        output['ENTRYPOINT'] = re.sub('["\[\]]','',entrypoint[0]) if entrypoint != [] else None
        output['MAINTAINER'] = maintainer[0] if maintainer != [] else None
        output['USER'] = duser[0] if duser != [] else 'root'
    except Exception, e:
        print '(Cannot get Dockerfile >>>%s)'% e
        for key in ('FROM', 'CMD', 'ENV', 'VOL', 'WDIR', 'PORTS', 'ENTRYPOINT', 'MAINTAINER', 'USER'): output[key] = None
    return output

def get_customdockerfile_details(filename):
    output = {}
    try:
        with open(filename, 'r') as f:
            dockerfile = f.read()
        dockerfile = dockerfile.replace('\\\n', ' ')
        f = [a[1] for a in re.findall(r'(FROM|from)\s+(.*)', dockerfile)][0]
        maintainer = [a[1] for a in re.findall(r'(MAINTAINER|maintainer)\s+(.*)', dockerfile)]
        lines = re.findall(r'\n(COPY|copy|ADD|add|RUN|run|WORKDIR|workdir|ENV|env)\s+(.*)', dockerfile)
        cmds = [a[1] for a in re.findall(r'\n(CMD|cmd)\s+(.*)', dockerfile)]
        envs = [a[1] for a in re.findall(r'\n(ENV|env)\s+(.*)', dockerfile)]
        volumes = [a[1] for a in re.findall(r'\n(volume|VOLUME)\s+(.*)', dockerfile)]
        wdir = [a[1] for a in re.findall(r'\n(workdir|WORKDIR)\s+(.*)', dockerfile)]
        ports = [a[1] for a in re.findall(r'\n(expose|EXPOSE)\s+(.*)', dockerfile)]
        duser = [a[1] for a in re.findall(r'\n(user|USER)\s+(.*)', dockerfile)]
        entrypoint = [a[1] for a in re.findall(r'\n(ENTRYPOINT|entrypoint)\s+(.*)', dockerfile)]
        output = {'FROM': f,
                  'lines': lines,
                 'ENV': envs,
                 'VOL': volumes,
                 'PORTS': ports}
        try:
            output['CMD'] = json.loads(cmds[0])
        except:
            output['CMD'] = cmds
        output['WDIR'] = wdir[0] if wdir != [] else None
        output['ENTRYPOINT'] = re.sub('["\[\]]','',entrypoint[0]) if entrypoint != [] else None
        output['MAINTAINER'] = maintainer[0] if maintainer != [] else None
        output['USER'] = duser[0] if duser != [] else 'root'
    except Exception, e:
        print '(%s)'% e
        for key in ('FROM', 'CMD', 'ENV', 'VOL', 'WDIR', 'PORTS', 'ENTRYPOINT', 'MAINTAINER', 'USER'): output[key] = None
    return output

def get_startup_commands(parsed, customs, defaults, rootdir, custom_exports):
    script = []

    exports = get_envs(parsed)
    if len(exports) > 0:
        script.append(get_envs(parsed))

    if custom_exports is not None:
        script.append(get_custom_envs(custom_exports))

    if customs['wdir'] is not None:
        script.append('cd %s ;'% customs['wdir'])
    else:
        if parsed['WDIR'] is not None:
            if len(parsed['WDIR']) > 0:
                script.append('cd %s \n'% parsed['WDIR'])
        else:
            script.append('cd %s ;'% defaults['wdir'])

    if customs['entrypoint'] is not None:
            script.append('%s '% customs['entrypoint'])
    else:
        if parsed['ENTRYPOINT'] is not None:
            if len(parsed['ENTRYPOINT']) > 0:
                script.append('%s '% parsed['ENTRYPOINT'])
        else:
            if customs['cmd'] is None and parsed['CMD'] is None:
                if os.path.isfile(os.path.join(rootdir,'entrypoint.sh')):
                    script.append('%s'% defaults['entrypoint'])

    if customs['cmd'] is not None:
        script.append('%s'% customs['cmd'])
    else:
        if parsed['CMD'] is not None:
            if len(parsed['CMD']) > 0:
                for cmd in range(len(parsed['CMD'])):
                    script.append('%s'% parsed['CMD'][cmd])
        else:
            script.append('%s'% defaults['cmd'])
    return script

def sanitize_image(raw_image):
    try:
        if len(raw_image.rsplit(':',-1)) == 2:
            userrepo, tag = raw_image.rsplit(':',-1)
        else:
            userrepo, tag = raw_image, None
        if len(userrepo.rstrip('/').lstrip('/').split('/')) == 2:
            user, repo = userrepo.rstrip('/').lstrip('/').split('/')
        else:
            user, repo = '_', userrepo.rstrip('/').lstrip('/')
        user, repo = re.sub('/','',user), re.sub('/','',repo)
        if user == '_' and tag is not None:
            image = '%s:%s'% (repo,tag)
        else:
            if user == '_' and tag is None:
                image = '%s'% repo
            else:
                if user != '_' and tag is None:
                    image = '%s/%s'% (user, repo)
                else:
                    image = '%s/%s:%s'% (user, repo, tag)
        return {'user':user, 'repo':repo, 'tag':tag, 'image':image}
    except:
        exit('ERROR: Image name format not supported')

def pullimage(image, rootdir):
    pulldocker = get_pulldocker_bin(bin_filename)
    try:
        if rootdir is not None:
            return subprocess.call([pulldocker,'-o', '%s'% rootdir, '%s'% image])
        else:
            return subprocess.call([pulldocker,image['image']])
    except Exception, e:
        print '(%s)'% e
        return False

def get_rootdir(image, custom_dir):
    if custom_dir is None:
        if image['user'] == '_':
            if image['tag'] is None:
                return image['repo']
            else:
                return '%s:%s'%(image['repo'], image['tag'])
        else:
                return image['image']
    else:
        if custom_dir[0] != '/':
            custom_dir = os.path.join(os.getcwd(),custom_dir)
        if os.path.isdir(custom_dir):
            return custom_dir
        else:
            exit('ERROR: rootdir not found')

def get_user(parsed, custom_user):
    if custom_user is None:
        if parsed['USER'] is None:
            return defaults['user']
        else:
            return parsed['USER']
    else:
        return custom_user

def get_envs(parsed):
    exports = ''
    envs = parsed['ENV']
    if envs is not None:
        for env in envs:
          e, val = re.split('\s+', env, 1)
          exports += 'export %s=\"%s\"; ' % (e, val)
    return exports

def get_custom_envs(custom_exports):
    exports = ''
    envs = custom_exports.split(',')
    for env in range(len(envs)):
        e,val =  envs[env].split('=')
        exports = exports + 'export %s=\"%s\"; '% (e, val)
    return exports

def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

def make_startup_script(runscript, comms):
    print runscript
    if os.path.exists(runscript):
        print 'Docker startup script ' + runscript + ' already exists - Overwriting'
    try:
        with open(runscript, 'w') as f:
            for line in comms:
                f.write(line)
        os.chmod(runscript, 0755)
    except Exception, e:
        exit('ERROR: Cannot write %s script (%s)'% (runscript,e))

def write_bashrc(bashrc, string):
    with open(bashrc, "a") as file:
        file.write('\n')
        file.write(string)
        file.write('\n')
        file.close()

def mount_binds(rootdir):
    chrootdir = os.path.join(os.getcwd(),rootdir)
    #mkdir_p(os.path.join(chrootdir,'/CL/readonly'))
    #subprocess.call(['mount', '--bind', '/CL/readonly', '%s'% os.path.join(chrootdir,'/CL/readonly')])
    subprocess.call(['mount', '--bind', '/dev', '%s'% os.path.join(chrootdir,'dev')])
    subprocess.call(['mount', '--bind', '/dev/pts', '%s'% os.path.join(chrootdir,'dev/pts')])
    subprocess.call(['mount', '--bind', '/sys', '%s'% os.path.join(chrootdir,'sys')])
    subprocess.call(['mount', '--bind', '/dev/pts', '%s'% os.path.join(chrootdir,'dev/pts')])
    subprocess.call(['mount', '--bind', '/run', '%s'% os.path.join(chrootdir,'run')])
    subprocess.call(['mount', '--bind', '/run/lock', '%s'% os.path.join(chrootdir,'run/lock')])
    subprocess.call(['mount', '--bind', '/run/user', '%s'% os.path.join(chrootdir,'run/user')])

def run_in_tab(tab,command):
    sendmessage='/srv/cloudlabs/scripts/send_message.sh CLIENTMESSAGE'
    data_j = json.dumps({'type':'write_to_term', 'id':str(tab), 'data':'%s \n'% command, 'to':'computer'})
    data = '%s \'%s\''% (sendmessage, data_j)
    subprocess.Popen([data], shell=True)

def install_pulldocker():
    url = 'https://www.terminal.com/pulldocker.tgz'
    try:
        subprocess.call(['wget', '--no-check-certificate', url])
        tfile = tarfile.open("pulldocker.tgz", 'r:gz')
        tfile.extractall('.')
        shutil.copy2('pulldocker','/usr/local/bin/pulldocker')
        os.chmod('/usr/local/bin/pulldocker',0755)
        os.remove('pulldocker')
        os.remove('pulldocker.tgz')
    except Exception, e:
        exit('ERROR: Cannot install pulldocker - (%s) \n please install it manually and try again'% e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.description='RUNIMAGE - Run a docker image inside a Terminal, using a chroot jail and without Docker'
    parser.add_argument('image', type=str, help='Docker image to be dumped')
    parser.add_argument('-u', '--user', type=str, default=None ,help='Run the container with a custom user [%s]'% defaults['user'])
    parser.add_argument('-e', '--entrypoint', type=str, default=None, help='Entrypoint bin/script [%s]'% defaults['entrypoint'])
    parser.add_argument('-c', '--cmd', type=str, default=None, help='Command/argument executed by the entrypoint [%s]'% defaults['cmd'])
    parser.add_argument('-D', '--rootdir', type=str, default=None, help='Custom path to run/pull the docker image')
    parser.add_argument('-d', '--wdir', type=str, default=None, help='Custom internal work dir')
    parser.add_argument('-f', '--dockerfile', type=str, default=None, help='Custom dockerfile')
    parser.add_argument('-w', '--overwrite', type=bool, default=False, help='DANGER - Overwrite image if it already exists')
    parser.add_argument('-t', '--tab', type=int, default=2, help='Terminal tab where the image will be mounted and executed')
    parser.add_argument('-n', '--nomounts', type=bool, default=False, help='Do NOT mount any additional FS. [FALSE]')
    parser.add_argument('-x', '--custom_exports', type=str, default=None, help='List of additional exported variable values /var=value/ comma separated.')

    args = vars(parser.parse_args())


    print 'Analyzing container information...'
    image=sanitize_image(args['image'])
    parsed_dockerfile = get_customdockerfile_details(args['dockerfile']) if args['dockerfile'] is not None else get_dockerfile_details(image['user'],image['repo'])
    rootdir = get_rootdir(image, args['rootdir'])
    runscript = '/run.sh'
    user = get_user(parsed_dockerfile,args['user'])
    script_array = get_startup_commands(parsed_dockerfile, args, defaults, rootdir, args['custom_exports'])

    print'Pulling image from dockerhub...'
    if os.path.exists(rootdir) is not True:
        print 'Pulling %s...'% image['image']
        pullimage(image['image'],rootdir)
        prepare = True
    else:
        if args['overwrite'] is True:
            os.rename(rootdir,'%s_BCK'% rootdir)
            print 'Pulling %s...'% image['image']
            pullimage(image['image'],rootdir)
            prepare = True
        else:
            prepare = False
            print '%s already exists. Not pulling.'%rootdir

    print 'Preparing jail...'
    if prepare is True or args['overwrite'] is True:
        # write_bashrc('/root/.bashrc','/usr/sbin/chroot %s'% rootdir)
        # write_bashrc('/root/.bashrc','mount -t proc proc /proc')
        shutil.copy2('/etc/resolv.conf', os.path.join(os.getcwd(), rootdir, 'etc/resolv.conf'))
    if args['nomounts'] is False:
        mount_binds(rootdir)
    make_startup_script('%s/%s/%s'% (os.getcwd(),rootdir,runscript), script_array)

    print 'Executing chrooted Jail in a new tab...'
    time.sleep(1)
    cmdchain = 'su -l %s -c %s'% (user,runscript)
    run_in_tab(args['tab'], '/usr/sbin/chroot %s'% rootdir)
    time.sleep(2)
    if args['nomounts'] is False:
        run_in_tab(args['tab'], 'mount -t proc proc /proc')
        time.sleep(1)
    run_in_tab(args['tab'], cmdchain)

    # Install permanent Jail :)
    #write_bashrc('/root/.bashrc','/usr/sbin/chroot %s'% rootdir)