#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <net/if.h>
#include <linux/sockios.h>
#include <sys/ioctl.h>

#define PRIVATE_SETVF    0x03
#define VF_UP             0x01
#define VF_DOWN           0x00
#define SUCCESS           0
#define SIOCDEVPRIINFO   0x89FE
#define MAXLEN            1024


FILE *logfile = NULL;
/* for passing single values */
struct private_value{
    unsigned int	cmd;
    unsigned int	data;
};
static send_ioctl(const char* ifname, struct private_value *pval)
{
    struct ifreq ifr;
    int fd, ret;
    
    /* Setup our control structures. */
    strcpy(ifr.ifr_name, ifname);
    
    /* Open control socket. */
    fd = socket(AF_INET, SOCK_DGRAM, 0);
    if (fd < 0) 
    {
        fputs("socket FAIL\n", logfile);
        return -1;
    }

    ifr.ifr_data = (caddr_t)pval;
    ret = ioctl(fd, SIOCDEVPRIINFO, &ifr);  
    if(ret)
    {
        close(fd);
        fputs("ioctl FAIL\n", logfile);
        return -1;
    } 
    
    close(fd);
    return 0;
}

static SendMsgToVF(char* ifname, struct private_value *pval)
{
    int ret;
    ret = send_ioctl(ifname,pval);
    return ret;
}

int main(int argc, char *argv[])
{
   
    unsigned char buf[MAXLEN];    
    struct private_value vf_data;
    
    memset(&vf_data,0,sizeof(vf_data));

    if ((argv[1] == NULL) || (argv[2] == NULL) || (argv[3] == NULL))
    {
        exit(1);
    }
    
    logfile = fopen(argv[3], "ab+" );

    if(logfile == NULL)
    {
         printf("%s, %s",argv[3],"not exit\n");
         exit(1);
    }
    // Ö±½ÓÉèÖÃ    
    vf_data.cmd = PRIVATE_SETVF;
    if ((0 == strcmp(argv[2], "UP"))||(0 == strcmp(argv[2], "up")))
    {
        vf_data.data = VF_UP;
        fprintf(logfile, "need to make %s up\n", argv[1]);
    }
    else if ((0 == strcmp(argv[2], "DOWN"))||(0 == strcmp(argv[2], "down")))
    {
        vf_data.data = VF_DOWN;
        fprintf(logfile, "need to make %s down\n", argv[1]);
    }
    else
    {
        fputs("wrong vf status\n", logfile);
        fclose(logfile);
        return -1;
    }
    if(SUCCESS != SendMsgToVF(argv[1], &vf_data))
    {
        fclose(logfile);
        logfile = NULL;
        return -1;
    }
    fclose(logfile);
    logfile = NULL;
    return 0;
}

