import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
import os
import sys
import traceback
import logging
import subprocess

class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = 'NombreDeTuServicio'
    _svc_display_name_ = 'Nombre Descriptivo de Tu Servicio'
    _svc_description_ = 'Descripción breve de lo que hace tu servicio'

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        # Configurar logging
        LOG_FILENAME = 'C:\\ruta\\a\\tu\\logfile.log'
        logging.basicConfig(
            filename=LOG_FILENAME,
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STOPPED,
            (self._svc_name_, '')
        )
        logging.info(f"Servicio {self._svc_name_} detenido.")
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        logging.info(f"Servicio {self._svc_name_} iniciado.")
        self.main()

    def main(self):
        try:
            script_path = os.path.abspath("app.py")
            subprocess.run(['python', script_path], check=True)
        except Exception as e:
            error_msg = f"Error en el servicio {self._svc_name_}: {str(e)}\n{traceback.format_exc()}"
            servicemanager.LogErrorMsg(error_msg)
            logging.error(error_msg)
            self.SvcStop()

if __name__ == '__main__':
    if len(sys.argv) == 1:
        # Ejecutar como servicio
        win32serviceutil.HandleCommandLine(AppServerSvc)
    else:
        # Manejar instalación con opciones personalizadas
        win32serviceutil.HandleCommandLine(
            AppServerSvc,
            serviceClassString='tu_script_servicio.AppServerSvc',
            argv=sys.argv
        )
