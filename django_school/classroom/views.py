from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponse
from django.urls import reverse

from teachers.decorators import teacher_required
from students.models import Student
from schools.models import AcademicYear

from .models import ClassRoom, Subject, Period, Attendance, AttendanceClass
from .forms import ClassroomForm,PeriodForm, SubjectForm

def get_timetable_periods(classroom):
    color_list = ['#008744','#0057e7','#d62d20','#ffa700','#ffffff',
            '#96ceb4','#ffeead','#ff6f69','#ffcc5c','#88d8b0',
            '#ffb3ba','#ffdfba','#ffffba','#baffc9','#bae1ff',]
    
    periods = Period.objects.filter(classroom= classroom)
    return [{
        'id':p.id, 
        'title':'{0} ({1})'.format(p.subject.name, p.teacher.username), 
        'start':p.startdatetime,
        'end':p.enddatetime,
        'color': color_list[p.subject.id % len(color_list)]
        } for p in periods]

# Create your views here.
@method_decorator([login_required,teacher_required], name='dispatch')
class TimeTableView(View):
    def get(self, request):
        school = request.user.school
        classroom_name = request.GET.get('classroom','')
        
        if classroom_name: 
            classroom = ClassRoom.objects.get(school = school, name = classroom_name)
            qs_json = get_timetable_periods(classroom)
            return JsonResponse(qs_json,safe=False)
        
        resp = {
            'classrooms': ClassRoom.objects.filter(school = school),
            'subjects': Subject.objects.filter(school = school),
            'teachers': get_user_model().objects.filter(school = school, user_type=2),
        }
        
        return render(request,'classroom/timetable.html', resp)

    def post(self,request):
        """
        Save a Period of TimeTable
        """
        # classroom, subject, teacher, day, starttime,endtime
        school = request.user.school
        DAY_CHOICES = {n[1]: n[0] for n in Period._meta.get_field('dayoftheweek').choices}
        updated_request = request.POST.copy()
        updated_request['classroom'] = ClassRoom.objects.get(school = school,name=updated_request['classroom']).id
        updated_request['dayoftheweek'] = DAY_CHOICES[updated_request['dayoftheweek']]
        form = PeriodForm(updated_request)
        if form.is_valid():
            form.save()
            message = 'success'
        else:
            message = str(form.errors)

        return HttpResponse(message)


@method_decorator([login_required,teacher_required], name='dispatch')
class AttendanceView(View):
    def get(self, request):
        school = request.user.school
        classrooms = ClassRoom.objects.filter(school=school).order_by('name')
        resp = {'classrooms': classrooms, 'students': None, 'attendances': None}

        att_classroom = request.GET.get('classroom','')
        att_date = request.GET.get('date','')
        if att_classroom:
            resp['att_classroom'] = int(att_classroom)
        resp['att_date'] = att_date
        if att_classroom and att_date:
            # dt = datetime.strptime(att_date, "%d/%m/%Y")
            attendance_config = AttendanceClass.objects.filter(
                academicyear__status = True,
                classroom_id = att_classroom,
                date = datetime.strptime(att_date, '%d/%m/%Y')
            )
            resp['students'] = Student.objects.filter(classroom_id = att_classroom)
            if attendance_config:

                resp['attendances'] = attendance_config[0].attendance_set.all()

            # resp['attendance_status_choices'] = Attendance.ATTENDANCE_STATUS_CHOICES
            # Period.objects.filter(classroom_id = request.GET['classroom'],
            #    dayoftheweek = dt.weekday()).order_by('starttime')
            # print(resp['students'].values())
        return render(request,'classroom/attendance.html', resp)

    def post(self,request):
        """
        Add / Edit attendance entries
        """ 
        att_classroom = request.POST['classroom']
        att_date = request.POST['date']
        # datetime.strptime("2013-1-25", '%d/%m/%Y').strftime('%Y-%m-%d')
        attendance_config, _ = AttendanceClass.objects.get_or_create(
            academicyear = AcademicYear.objects.get(status=True),
            classroom_id = att_classroom,
            date = datetime.strptime(att_date, '%d/%m/%Y')
            )
        for student in Student.objects.filter(classroom_id = att_classroom):
            status = request.POST[str(student.user.id)]
            if status == 'present':
                status = 'P'
            else:
                status = 'A'

            Attendance.objects.update_or_create(
                attendanceclass=attendance_config,
                student=student,
                defaults={'status':status})
        # Attendance
        
        # for i, s in enumerate(cl.student_set.all()):
        # status = request.POST[s.USN]
        messages.success(request, 'Attendance details saved with success!')
        return redirect(reverse('classroom:attendance'))

@method_decorator([login_required,teacher_required], name='dispatch')
class AttendanceReportView(View):
    def generate_report(self,att_class):
        from collections import defaultdict
        #[
        #   {'1': ['Suhail', 'a', 'p', 'p']]}
        attendances = defaultdict(list)
        for att in att_class:
            for attendance in att.attendance_set.all():
                print('day:', att.date.day,attendance.student.user.username, attendance.status)
                attendances[attendance.student.user.id].insert(att.date.day,attendance.status)

        
        print(attendances)
        return att_class

    def get(self, request):
        school = request.user.school
        classrooms = ClassRoom.objects.filter(school=school).order_by('name')
        resp = {'classrooms': classrooms, 'academicyears': AcademicYear.objects.all(), 'attendances': None,
            'months': ['January','February','March','April','May','June','July','August','September','October','November','December']}

        att_classroom = request.GET.get('classroom','')
        att_year = request.GET.get('academicyear','')
        att_month = request.GET.get('month','')
        if att_classroom:
            resp['att_classroom'] = int(att_classroom)
        if att_year:
            resp['att_year'] = int(att_year)
        if att_month:
            resp['att_month'] = int(att_month)

        if att_classroom and att_year and att_month:
            # dt = datetime.strptime(att_date, "%d/%m/%Y")
            att_class = AttendanceClass.objects.filter(
                academicyear_id = att_year,
                classroom_id = att_classroom,
                date__month = att_month
            ).order_by('date')
            resp['attendances'] = self.generate_report(att_class)
        return render(request,'classroom/attendancereport.html', resp)

@login_required
@teacher_required
def delete_period(request):
    p = Period.objects.get(id=request.GET['period']).delete()
    return HttpResponse('success')

@login_required
@teacher_required
def classroom_view(request):
    if request.method == 'POST':
        form = ClassroomForm(request.POST)
        if form.is_valid():
            classroom = form.save(commit=False)
            classroom.school = request.user.school
            classroom.save()
            messages.success(request, 'ClassRoom saved with success!')
            return redirect('classroom:classrooms')
    else:
        classroom = ClassRoom(school = request.user.school)
        form = ClassroomForm(instance=classroom)

    classrooms = ClassRoom.objects.filter(school = request.user.school)
    return render(request,"classroom/classrooms.html", {'form': form, 'classrooms':classrooms })

@login_required
@teacher_required
def subject_view(request):
    if request.method == 'POST':
        form = SubjectForm(request.POST)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.school = request.user.school
            subject.save()
            messages.success(request, 'Subject saved with success!')
            return redirect('classroom:subjects')
    else:
        subject = Subject(school = request.user.school)
        form = SubjectForm(instance=subject)

    subjects = Subject.objects.filter(school = request.user.school)
    return render(request,"classroom/subjects.html", {'form': form, 'subjects':subjects })
