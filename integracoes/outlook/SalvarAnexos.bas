Attribute VB_Name = "ThisOutlookSession"
' ════════════════════════════════════════════════════════════════════════════
' Salva automaticamente os anexos dos relatórios agendados do CRM numa pasta
' organizada por dia, no formato que o relatorio_backlog espera:
'
'     <PASTA_BASE>\<Mês>\<DD-MM>\Backlog DD-MM-AAAA.xlsx
'
' Instalação: Outlook (desktop) > Alt+F11 > ThisOutlookSession > colar este
' código > ajustar as duas constantes abaixo > salvar e reiniciar o Outlook.
' ════════════════════════════════════════════════════════════════════════════
Option Explicit

' >>> AJUSTE AQUI <<<
Private Const PASTA_BASE As String = "C:\caminho\para\dados"
Private Const PALAVRA_CHAVE As String = "Backlog"   ' trecho presente no nome dos anexos do CRM

' Disparado a cada e-mail novo.
Private Sub Application_NewMailEx(ByVal EntryIDCollection As String)
    Dim ids() As String, i As Long, item As Object
    ids = Split(EntryIDCollection, ",")
    For i = LBound(ids) To UBound(ids)
        Set item = Application.Session.GetItemFromID(ids(i))
        If TypeName(item) = "MailItem" Then ProcessarEmail item
    Next i
End Sub

Private Sub ProcessarEmail(ByVal mail As Outlook.MailItem)
    Dim anexo As Outlook.Attachment, pasta As String
    For Each anexo In mail.Attachments
        If InStr(1, anexo.FileName, PALAVRA_CHAVE, vbTextCompare) > 0 _
           Or InStr(1, anexo.FileName, "fechados", vbTextCompare) > 0 Then
            If LCase$(Right$(anexo.FileName, 5)) = ".xlsx" Then
                pasta = PastaDaData(DataDoArquivo(anexo.FileName, mail.ReceivedTime))
                GarantirPasta pasta
                anexo.SaveAsFile pasta & "\" & anexo.FileName
            End If
        End If
    Next anexo
End Sub

' Usa a data embutida no nome (DD-MM-AAAA); se não houver, a data de recebimento.
Private Function DataDoArquivo(ByVal nome As String, ByVal recebido As Date) As Date
    Dim re As Object, m As Object
    Set re = CreateObject("VBScript.RegExp")
    re.Pattern = "(\d{2})[-_.](\d{2})[-_.](\d{4})"
    If re.Test(nome) Then
        Set m = re.Execute(nome)(0)
        DataDoArquivo = DateSerial(CInt(m.SubMatches(2)), CInt(m.SubMatches(1)), CInt(m.SubMatches(0)))
    Else
        DataDoArquivo = DateValue(recebido)
    End If
End Function

Private Function PastaDaData(ByVal d As Date) As String
    Dim meses As Variant
    meses = Array("Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", _
                  "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro")
    PastaDaData = PASTA_BASE & "\" & meses(Month(d) - 1) & "\" & Format(d, "dd-mm")
End Function

' Cria a pasta e as intermediárias, se não existirem.
Private Sub GarantirPasta(ByVal caminho As String)
    Dim partes() As String, atual As String, i As Long
    partes = Split(caminho, "\")
    atual = partes(0)
    For i = 1 To UBound(partes)
        atual = atual & "\" & partes(i)
        If Dir(atual, vbDirectory) = "" Then MkDir atual
    Next i
End Sub

' Rode manualmente (Alt+F8) para reprocessar os e-mails que já estão na Caixa de Entrada.
Public Sub ProcessarCaixaDeEntrada()
    Dim item As Object
    For Each item In Application.Session.GetDefaultFolder(olFolderInbox).Items
        If TypeName(item) = "MailItem" Then ProcessarEmail item
    Next item
    MsgBox "Anexos reprocessados.", vbInformation
End Sub
